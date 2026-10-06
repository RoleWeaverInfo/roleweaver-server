"""Local web installer for an existing Linux NWN/NWNX server.

The browser is only a front end. Profiles, checks, bundles and service changes use
the same modules as ``bash setup.sh``. The listener is deliberately loopback-only
and every API request needs the random token printed to the terminal.
"""

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import install_bundle as bundles
import install_profile as profiles
import manage_installation as manager
import server_setup

STATE = {
    "running": False,
    "action": "",
    "world": "",
    "started": 0,
    "finished": 0,
    "ok": None,
    "log": "",
}
STATE_LOCK = threading.Lock()
ACTION_LOCK = threading.Lock()


def public_profile(profile):
    """Return non-secret setup information suitable for the browser."""
    if profile is None:
        return None
    return {
        "version": profile["version"],
        "world_id": profile["world_id"],
        "redis_prefix": profile["redis_prefix"],
        "redis_port": profile["redis_port"],
        "dashboard_port": profile["dashboard_port"],
        "paths": profile["paths"],
        "resources": profile["resources"],
        "features": profile["features"],
        "progress": profile["progress"],
        "installed": (
            profiles.installation(profile["world_id"]) / "config.json"
        ).is_file(),
    }


def available_worlds():
    result = []
    for path in sorted(profiles.profile_directory().glob("*.json")):
        try:
            result.append(public_profile(profiles.load(path.stem)))
        except (OSError, ValueError, json.JSONDecodeError):
            result.append({"world_id": path.stem, "invalid": True})
    return result


def initial_profile(world="my_world"):
    paths = profiles.defaults()
    discovered = profiles.discover()
    if len(discovered) == 1:
        paths.update({k: v for k, v in discovered[0].items() if v})
    server_home = Path(paths["server_home"])
    modules = sorted((server_home / "modules").glob("*.mod"))
    if len(modules) == 1:
        paths["module"] = str(modules[0])
    resources = []
    override = server_home / "override"
    if override.is_dir():
        resources.append(str(override))
    return {
        "version": 1,
        "world_id": world,
        "redis_prefix": "roleweaver:" + world,
        "redis_port": 6379,
        "dashboard_port": 8743,
        "paths": paths,
        "features": dict.fromkeys(profiles.FEATURES, False),
        "resources": resources,
        "progress": {},
    }


def clean_path(value, optional=False):
    if not isinstance(value, str) or any(c in value for c in '\n\r\0"%\\'):
        raise ValueError(
            "Use Linux paths without control characters, quotes, percent or backslashes"
        )
    if not value and optional:
        return ""
    path = Path(value).expanduser()
    return str(path.resolve())


def save_profile(payload):
    if not isinstance(payload, dict):
        raise ValueError("Invalid configuration")
    world = profiles.identifier(payload.get("world_id", ""))
    previous = profiles.load(world) if profiles.profile_path(world).exists() else None
    paths = payload.get("paths", {})
    if set(paths) != set(profiles.PATHS):
        raise ValueError("Complete all server path fields")
    normalized = {
        key: clean_path(value, optional=key == "compiler")
        for key, value in paths.items()
    }
    features = payload.get("features", {})
    profile = {
        "version": 1,
        "world_id": world,
        "redis_prefix": payload.get("redis_prefix", "roleweaver:" + world),
        "redis_port": int(payload.get("redis_port", 6379)),
        "dashboard_port": int(payload.get("dashboard_port", 8743)),
        "paths": normalized,
        "features": {key: bool(features.get(key, False)) for key in profiles.FEATURES},
        "resources": [clean_path(v) for v in payload.get("resources", []) if v],
        "progress": dict(previous["progress"]) if previous else {},
    }
    profiles.validate(profile)
    profiles.installed_settings(profile)
    profiles.save(profile)
    return profile


def run_action(action, world):
    with ACTION_LOCK:
        output = io.StringIO()
        ok = False
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                profile = profiles.load(world)
                if action == "check":
                    rows = profiles.checks(profile)
                    for row in rows:
                        print(
                            f"[{row['status'].upper()}] {row['name']}: {row['detail']}"
                        )
                    ok = not any(row["status"] == "fix" for row in rows)
                elif action == "prepare":
                    if any(row["status"] == "fix" for row in profiles.checks(profile)):
                        raise ValueError(
                            "Resolve prerequisite errors before preparing the bridge"
                        )
                    target = (
                        bundles.prepare(profile)
                        if not bundles.current(profile)
                        else Path(profile["progress"]["bundle"])
                    )
                    print("Prepared integration bundle:", target)
                    print("Follow:", target / "INSTALL.md")
                    ok = True
                elif action in ("install", "update"):
                    rows = profiles.checks(profile)
                    if any(row["status"] == "fix" for row in rows):
                        raise ValueError(
                            "Resolve prerequisite errors before changing the service"
                        )
                    if not bundles.current(profile):
                        bundles.prepare(profile)
                    manager.apply(profile, update=action == "update")
                    ok = True
                elif action == "restart":
                    profiles.installed_settings(profile)
                    manager.own_service(profile)
                    manager.run(
                        ["systemctl", "--user", "restart", manager.unit_name(profile)]
                    )
                    ok = server_setup.verify(profile)
                elif action == "verify":
                    ok = server_setup.verify(profile)
                elif action == "rollback":
                    manager.rollback(profile)
                    ok = True
                else:
                    raise ValueError("Unsupported setup action")
        except Exception as exc:  # Returned to the local administrator with context.
            print(f"\nSetup stopped: {exc}", file=output)
        finally:
            with STATE_LOCK:
                STATE.update(
                    running=False,
                    finished=int(time.time()),
                    ok=ok,
                    log=output.getvalue()[-100_000:],
                )


def begin_action(action, world):
    profiles.identifier(world)
    profiles.load(world)
    with STATE_LOCK:
        if STATE["running"]:
            raise ValueError("Another setup operation is already running")
        STATE.update(
            running=True,
            action=action,
            world=world,
            started=int(time.time()),
            finished=0,
            ok=None,
            log="Starting…\n",
        )
    threading.Thread(target=run_action, args=(action, world), daemon=True).start()


HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Role Weaver Setup</title>
<style>
:root{color-scheme:dark;--bg:#101018;--panel:#1b1b28;--gold:#d7a94b;--ink:#f4f0e8;--muted:#aaa7b5;--good:#67c587;--bad:#ef7373;--warn:#e4bd60}*{box-sizing:border-box}body{margin:0;background:linear-gradient(145deg,#0d0d13,#181522);color:var(--ink);font:15px system-ui,sans-serif}header{padding:22px 28px;border-bottom:1px solid #4c3b22;background:#111018}header h1{margin:0;color:var(--gold);font-family:Georgia,serif}header p{margin:5px 0 0;color:var(--muted)}main{max-width:1100px;margin:auto;padding:24px}.steps{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}.steps button,.actions button{border:1px solid #65502d;background:#242032;color:var(--ink);padding:10px 14px;border-radius:7px;cursor:pointer}.steps button.active,.actions button.primary{background:#6c4a16;color:#fff3d6}.card{display:none;background:var(--panel);border:1px solid #353044;border-radius:10px;padding:22px;box-shadow:0 10px 28px #0005}.card.active{display:block}h2{margin-top:0;color:#f2d28d}label{display:block;margin:12px 0 5px;color:#d8d3df}input,select,textarea{width:100%;padding:10px;border-radius:6px;border:1px solid #4a4558;background:#11111a;color:var(--ink)}input[type=checkbox]{width:auto;margin-right:8px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}.feature{display:inline-block;width:48%;padding:7px 0}.hint{color:var(--muted);font-size:13px}.actions{display:flex;gap:9px;flex-wrap:wrap;margin-top:18px}.status{padding:10px;margin:8px 0;border-left:4px solid var(--warn);background:#12121b}.status.ok{border-color:var(--good)}.status.fix{border-color:var(--bad)}pre{white-space:pre-wrap;background:#0b0b10;border:1px solid #353044;padding:14px;border-radius:7px;max-height:430px;overflow:auto}.hidden{display:none}@media(max-width:700px){.grid{grid-template-columns:1fr}.feature{width:100%}}
</style></head><body>
<header><h1>Role Weaver Server Add-on</h1><p>Guided installation for an existing Linux NWN:EE/NWNX server</p></header>
<main><div class="steps"><button data-step="welcome" class="active">1 Welcome</button><button data-step="server">2 Server</button><button data-step="features">3 Features</button><button data-step="review">4 Check</button><button data-step="install">5 Install</button><button data-step="verify">6 Verify</button></div>
<section id="welcome" class="card active"><h2>Choose a world</h2><p>The installer keeps your module and NWNX installation in their existing locations. It will not restart NWN.</p><label>Saved installation</label><select id="worlds"></select><div class="actions"><button class="primary" onclick="loadWorld()">Open selected world</button><button onclick="newWorld()">Configure a new world</button></div><p class="hint">Settings are saved privately under ~/.config/roleweaver/installations/. API keys are not stored in the setup profile.</p></section>
<section id="server" class="card"><h2>Server and world</h2><div class="grid"><div><label>World ID</label><input id="world_id" pattern="[a-z][a-z0-9_]{0,23}"><label>NWN dedicated server root</label><input id="runtime"><label>World server home / userdirectory</label><input id="server_home"><label>Module file</label><input id="module"></div><div><label>NWNX plugin folder</label><input id="plugins"><label>NWNX header folder</label><input id="headers"><label>nwnsc compiler (optional)</label><input id="compiler"><label>Additional loose resource folders, one per line</label><textarea id="resources" rows="3"></textarea></div></div><div class="grid"><div><label>Dashboard port</label><input id="dashboard_port" type="number"></div><div><label>Redis port</label><input id="redis_port" type="number"></div></div><label>Redis prefix</label><input id="redis_prefix"><div class="actions"><button class="primary" onclick="saveAnd('features')">Save and continue</button></div></section>
<section id="features" class="card"><h2>Optional capabilities</h2><p>Basic AI NPC conversations are always included.</p><div id="featureList"></div><div class="actions"><button class="primary" onclick="saveAnd('review')">Save and check</button></div></section>
<section id="review" class="card"><h2>Compatibility check</h2><div id="checks"></div><div class="actions"><button onclick="runCheck()">Run checks again</button><button class="primary" onclick="prepare()">Prepare integration bundle</button></div><p class="hint">Preparation reads the module and creates a review bundle. It does not modify the module, launcher, plugins or running NWN server.</p></section>
<section id="install" class="card"><h2>Install or update Role Weaver</h2><p id="installText"></p><div class="actions"><button class="primary" onclick="serviceAction()" id="serviceButton">Install service</button><button onclick="doAction('rollback',true)">Roll back software</button></div><p class="hint">The service installer creates a recovery point and restores the earlier service if startup fails. It does not restart NWN.</p></section>
<section id="verify" class="card"><h2>Connection and maintenance</h2><div class="actions"><button class="primary" onclick="doAction('verify')">Verify game connection</button><button onclick="doAction('restart',true)">Restart Role Weaver</button></div><h3>Windows dashboard tunnel</h3><pre id="tunnel"></pre><h3>Setup activity</h3><pre id="log">No operation has run.</pre></section>
</main><script>
const token=new URLSearchParams(location.search).get('token')||'';let profile=null,installed=false;
const features={companions:'Player familiar and companion AI',dm_spawn:'DM spawning and encounters',persistent_spawn:'Persistent DM-created NPCs',merchants:'Merchant and shop integration',translation:'World text and dialogue translation',guardrails:'Local Guardrails AI dependency'};
async function api(path,options={}){options.headers={...(options.headers||{}),'X-Setup-Token':token};let r=await fetch(path,options),d=await r.json();if(!r.ok)throw new Error(d.error||'Request failed');return d}
function step(name){document.querySelectorAll('.card,.steps button').forEach(x=>x.classList.remove('active'));document.getElementById(name).classList.add('active');document.querySelector(`[data-step="${name}"]`).classList.add('active')}
document.querySelectorAll('.steps button').forEach(b=>b.onclick=()=>step(b.dataset.step));
function fill(p){profile=p;installed=!!p.installed;for(let k of ['world_id','redis_prefix','redis_port','dashboard_port'])document.getElementById(k).value=p[k];for(let k of ['runtime','server_home','module','plugins','headers','compiler'])document.getElementById(k).value=p.paths[k]||'';resources.value=(p.resources||[]).join('\n');featureList.innerHTML=Object.entries(features).map(([k,v])=>`<label class="feature"><input type="checkbox" id="f_${k}" ${p.features[k]?'checked':''}>${v}</label>`).join('');serviceButton.textContent=installed?'Update Role Weaver':'Install Role Weaver';installText.textContent=installed?'An existing installation was detected. Configuration, provider keys and player data will be preserved.':'A new managed Role Weaver service will be created for this world.';tunnel.textContent=`ssh -N -L ${p.dashboard_port}:127.0.0.1:${p.dashboard_port} YOUR_USER@YOUR_SERVER_IP\nThen open http://127.0.0.1:${p.dashboard_port}/`;}
function collect(){let paths={};for(let k of ['runtime','server_home','module','plugins','headers','compiler'])paths[k]=document.getElementById(k).value.trim();let fs={};for(let k in features)fs[k]=document.getElementById('f_'+k)?.checked||false;return {world_id:world_id.value.trim(),redis_prefix:redis_prefix.value.trim(),redis_port:Number(redis_port.value),dashboard_port:Number(dashboard_port.value),paths,features:fs,resources:resources.value.split('\n').map(x=>x.trim()).filter(Boolean)}}
async function init(){try{let d=await api('/api/state');worlds.innerHTML='<option value="">New installation</option>'+d.worlds.map(x=>`<option>${x.world_id}</option>`).join('');fill(d.initial);poll()}catch(e){alert(e.message)}}
async function loadWorld(){if(!worlds.value)return newWorld();let d=await api('/api/profile?world='+encodeURIComponent(worlds.value));fill(d.profile);step('server')}
async function newWorld(){let d=await api('/api/new');fill(d.profile);step('server')}
async function save(){let d=await api('/api/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(collect())});fill(d.profile);return d.profile}
async function saveAnd(next){try{await save();if(next==='review')await runCheck();step(next)}catch(e){alert(e.message)}}
function renderChecks(rows){checks.innerHTML=rows.map(r=>`<div class="status ${r.status}"><b>${r.status.toUpperCase()} — ${r.name}</b><br>${r.detail}</div>`).join('')}
async function runCheck(){try{await save();let d=await api('/api/check?world='+encodeURIComponent(profile.world_id));renderChecks(d.rows)}catch(e){alert(e.message)}}
async function prepare(){try{await save();await doAction('prepare',true);step('verify')}catch(e){alert(e.message)}}
async function serviceAction(){await doAction(installed?'update':'install',true);step('verify')}
async function doAction(action,confirm=false){if(confirm&&!window.confirm(`Proceed with ${action}? NWN itself will not be restarted.`))return;try{let d=await api('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({world:profile.world_id,action,confirmed:confirm})});log.textContent=d.status.log;step('verify')}catch(e){alert(e.message)}}
async function poll(){try{let d=await api('/api/operation');log.textContent=d.status.log||'No operation has run.';if(d.status.running)setTimeout(poll,1000);else setTimeout(poll,4000)}catch(e){setTimeout(poll,5000)}}
init();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "RoleWeaverSetup/1.0"

    def log_message(self, fmt, *args):
        print("Setup web:", fmt % args)

    def security_headers(self, content_type):
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'",
        )

    def json_response(self, value, status=HTTPStatus.OK):
        raw = json.dumps(value).encode()
        self.send_response(status)
        self.security_headers("application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def authorized(self, parsed):
        query = parse_qs(parsed.query)
        return secrets.compare_digest(
            self.headers.get("X-Setup-Token", "") or query.get("token", [""])[0],
            self.server.token,
        )

    def body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("Request is too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if not self.authorized(parsed):
            return self.json_response(
                {"error": "Invalid or missing setup token"}, HTTPStatus.FORBIDDEN
            )
        try:
            if parsed.path == "/":
                raw = HTML.encode()
                self.send_response(HTTPStatus.OK)
                self.security_headers("text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                return self.wfile.write(raw)
            if parsed.path == "/api/state":
                return self.json_response(
                    {
                        "worlds": available_worlds(),
                        "initial": public_profile(initial_profile()),
                    }
                )
            if parsed.path == "/api/new":
                return self.json_response(
                    {"profile": public_profile(initial_profile())}
                )
            if parsed.path == "/api/profile":
                world = parse_qs(parsed.query).get("world", [""])[0]
                return self.json_response(
                    {"profile": public_profile(profiles.load(world))}
                )
            if parsed.path == "/api/check":
                world = parse_qs(parsed.query).get("world", [""])[0]
                return self.json_response(
                    {"rows": profiles.checks(profiles.load(world))}
                )
            if parsed.path == "/api/operation":
                with STATE_LOCK:
                    return self.json_response({"status": dict(STATE)})
            return self.json_response({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            return self.json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_POST(self):
        parsed = urlparse(self.path)
        if not self.authorized(parsed):
            return self.json_response(
                {"error": "Invalid or missing setup token"}, HTTPStatus.FORBIDDEN
            )
        try:
            data = self.body()
            if parsed.path == "/api/profile":
                return self.json_response(
                    {"profile": public_profile(save_profile(data))}
                )
            if parsed.path == "/api/action":
                action = data.get("action", "")
                mutations = {"prepare", "install", "update", "restart", "rollback"}
                if action in mutations and data.get("confirmed") is not True:
                    raise ValueError("Confirm this operation in the installer")
                if action not in mutations | {"check", "verify"}:
                    raise ValueError("Unsupported setup action")
                begin_action(action, data.get("world", ""))
                with STATE_LOCK:
                    return self.json_response(
                        {"status": dict(STATE)}, HTTPStatus.ACCEPTED
                    )
            return self.json_response({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            return self.json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Local browser installer for Role Weaver"
    )
    parser.add_argument("--port", type=int, default=8750, help="loopback setup port")
    args = parser.parse_args(argv)
    if sys.platform != "linux":
        print("Run this installer on the Linux NWN server.")
        return 1
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("Run setup as the Linux account that owns NWN, not root or sudo.")
        return 1
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be from 1024 to 65535")
    os.umask(0o077)
    token = secrets.token_urlsafe(24)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.token = token
    print("\nRole Weaver graphical setup is running on this server only.")
    print("From another computer, open an SSH tunnel:")
    print(f"  ssh -N -L {args.port}:127.0.0.1:{args.port} YOUR_USER@YOUR_SERVER_IP")
    print("Then open:")
    print(f"  http://127.0.0.1:{args.port}/?token={token}")
    print("\nPress Ctrl+C to close setup. Installed services continue running.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSetup interface closed.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
