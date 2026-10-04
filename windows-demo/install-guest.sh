#!/usr/bin/env bash
# Run as the roleweaver user INSIDE the disposable QEMU guest, never on a PW host.
set -euo pipefail
if [[ "$(hostname)" != roleweaver-demo ]]; then
    echo 'This provisioner is only for the roleweaver-demo QEMU guest.' >&2
    exit 1
fi
cd "$HOME"
cloud-init status --wait
if ! command -v nft >/dev/null; then
    sudo apt-get update
    sudo apt-get install -y nftables
fi
test -f native.tar.gz
test -f RoleWeaver-Demo-1.0.0.tar.gz
if [[ ! -d native ]]; then tar -xzf native.tar.gz; fi
if [[ ! -d demo ]]; then
    mkdir demo
    tar -xzf RoleWeaver-Demo-1.0.0.tar.gz -C demo --strip-components=1
fi
cd demo
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements-guardrails.txt
if [[ ! -f .demo/qemu_demo/settings.json ]]; then
    # Demo 1.0.0 seeds its database before creating the player identity file.
    # Initialize only a new, empty instance; never repair an established identity.
    .venv/bin/python - <<'PY'
from pathlib import Path
import secrets
root = Path('.demo/qemu_demo/data')
root.mkdir(parents=True, exist_ok=True)
salt = root / 'identity_salt'
if not (root / 'roleweaver.sqlite3').exists() and not salt.exists():
    with salt.open('x') as f:
        f.write(secrets.token_hex(32))
    salt.chmod(0o600)
PY
    .venv/bin/python demo/demo.py setup --instance qemu_demo \
        --native "$HOME/native" --compiler "$HOME/native/nwnsc" \
        --game-port 5127 --web-port 8747 --guardrails
    .venv/bin/python - <<'PY'
import json
from pathlib import Path
from roleweaver.translation import TranslationCache
p = Path('.demo/qemu_demo/config.json')
config = json.loads(p.read_text())
config['world_name'] = 'Role Weaver Windows demo'
config['companions_enabled'] = True
p.write_text(json.dumps(config, indent=2) + '\n')
# The released 1.0.0 setup predates the demo's enabled translation default.
# This block runs only for a new instance. Keep an existing saved choice.
translation_path = Path('.demo/qemu_demo/data/translations.sqlite3')
if not translation_path.exists():
    cache = TranslationCache(translation_path)
    try:
        cache.configure(dict(cache.config(), enabled=True))
    finally:
        cache.db.close()
# This VM accepts connections only through Windows loopback. A standalone demo
# must also work when the NWN master server cannot validate accounts. Keep the
# normal DM password; this option concerns external account validation only.
# Do not overwrite settings from a previous launch or apply this to a PW server.
login = Path('.demo/qemu_demo/userdata/settings.tml')
if not login.exists():
    login.write_text(
        '[masterserver.key-authentication]\n'
        'mode = "if-reachable"\n'
        'enforce-on-private-networks = false\n'
    )
PY
fi
sudo tee /etc/roleweaver-qemu-udp.nft >/dev/null <<'EOF'
# This Windows libslirp build preserves 127.0.0.1 as the incoming UDP source.
# Linux rejects it on Ethernet. Rewrite only the demo's forwarded game packets
# to QEMU's host alias before routing, retaining the original player source port.
# The return path is handled by QEMU's existing UDP forwarding socket.
add table ip rw_qemu_udp
flush table ip rw_qemu_udp
table ip rw_qemu_udp {
 chain ingress {
  type filter hook prerouting priority raw; policy accept;
  iifname "enp0s2" ip saddr 127.0.0.1 ip daddr 10.0.2.15 udp dport 5127 ip saddr set 10.0.2.2 notrack counter
 }
 chain egress {
  type filter hook output priority raw; policy accept;
  ip daddr 10.0.2.2 udp sport 5127 notrack counter
 }
}
EOF
sudo tee /etc/systemd/system/roleweaver-qemu-network.service >/dev/null <<'EOF'
[Unit]
Description=QEMU local game UDP compatibility
Before=roleweaver-demo.service

[Service]
Type=oneshot
ExecStart=/usr/sbin/nft -f /etc/roleweaver-qemu-udp.nft
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
sudo tee /etc/systemd/system/roleweaver-demo.service >/dev/null <<EOF
[Unit]
Description=Role Weaver isolated QEMU demo
After=network-online.target redis-server.service roleweaver-qemu-network.service
Wants=network-online.target
Requires=redis-server.service roleweaver-qemu-network.service

[Service]
Type=simple
User=roleweaver
WorkingDirectory=$HOME/demo
Environment=NWNX_RWTRANSLATION_SKIP=n
ExecStart=$HOME/demo/.venv/bin/python demo/demo.py start --instance qemu_demo
KillSignal=SIGINT
KillMode=mixed
TimeoutStopSec=90
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
# The HTTP application retains its loopback binding and Host/Origin checks.
# QEMU exposes only host loopback port 8747, forwarding to this guest relay.
sudo tee /etc/systemd/system/roleweaver-dashboard-relay.service >/dev/null <<'EOF'
[Unit]
Description=Local QEMU dashboard relay
After=network.target

[Service]
User=roleweaver
ExecStart=/usr/bin/socat TCP-LISTEN:8748,bind=0.0.0.0,reuseaddr,fork TCP:127.0.0.1:8747
Restart=on-failure
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now roleweaver-qemu-network.service roleweaver-demo.service roleweaver-dashboard-relay.service
echo 'Demo services installed. No API keys or previous player data were imported.'
