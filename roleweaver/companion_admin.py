"""DM dashboard controls for familiars; never expose raw owner authentication IDs.

Profiles remain in the normal NPC store. The small backed-up administration record
holds the server switch and public character labels, not player preferences/items.
"""

import hashlib
import json
import re
import secrets
import time

from . import companion_templates
from .companion_templates import FIELDS


def is_companion(npc):
    return isinstance(npc, str) and bool(re.fullmatch(r"cp_[a-f0-9]{21}", npc))


def settings(raw=None):
    if raw is None:
        return dict(enabled=None, registry={})
    if (
        not isinstance(raw, dict)
        or set(raw) != {"enabled", "registry"}
        or (raw["enabled"] is not None and type(raw["enabled"]) is not bool)
        or not isinstance(raw["registry"], dict)
        or len(raw["registry"]) > 1000
    ):
        raise ValueError("Invalid companion administration settings")
    registry = {}
    for npc, value in raw["registry"].items():
        if (
            not is_companion(npc)
            or not isinstance(value, dict)
            or set(value) != {"owner_name", "creature", "species"}
            or any(not isinstance(v, str) or len(v) > 128 for v in value.values())
        ):
            raise ValueError("Invalid companion owner record")
        registry[npc] = dict(value)
    return dict(enabled=raw["enabled"], registry=registry)


def revision(profile):
    return hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()


class CompanionAdminService:
    def companions_enabled(self):
        saved = self.companion_admin["enabled"]
        return (
            bool(self.config.get("companions_enabled", False))
            if saved is None
            else saved
        )

    def remember_companion_owner(self, npc, event):
        """Only the public character name is retained; the CD key stays out."""
        record = dict(
            owner_name=event["owner"].partition(":")[2][:80],
            creature=event["creature"][:128],
            species=str(event.get("species", ""))[:80],
        )
        registry = self.companion_admin["registry"]
        if registry.get(npc) == record or (
            npc not in registry and len(registry) >= 1000
        ):
            return
        saved = dict(self.companion_admin, registry=dict(registry, **{npc: record}))
        self.set_setting("companion_admin", saved)
        self.companion_admin = saved

    def companion_dashboard(self):
        with self.lock:
            enabled = self.companions_enabled()
            hello = self.companion_admin_hello
            online = time.monotonic() - hello.get("seen", 0) < 5
            supported = hello.get("companion_admin_protocol") == 1
            applied = (
                hello.get("companion_enabled") == int(enabled)
                and hello.get("companion_generation") == self.companion_generation
            )
            status = (
                "offline"
                if not online
                else (
                    "upgrade_required"
                    if not supported
                    else "applied" if applied else "pending"
                )
            )
            rows = []
            for profile in self.store.list_npcs():
                npc = profile["id"]
                if not is_companion(npc):
                    continue
                state = self.companion_states.get(npc, {})
                connected = time.monotonic() - state.get("seen", 0) < 5
                owner = self.companion_admin["registry"].get(npc, {})
                rows.append(
                    dict(
                        id=npc,
                        name=profile["name"],
                        owner=owner.get("owner_name", ""),
                        creature=owner.get("creature", ""),
                        species=owner.get("species", ""),
                        connected=connected,
                        status=(
                            "Server AI disabled"
                            if not enabled
                            else (
                                "Not currently observed"
                                if not connected
                                else (
                                    "AI ready"
                                    if state.get("active") == 1
                                    else (
                                        "Player AI off"
                                        if state.get("opted_in") == 0
                                        else "AI unavailable: check combat, possession or player controls"
                                    )
                                )
                            )
                        ),
                        profile={k: profile[k] for k in FIELDS},
                        revision=revision(profile),
                        suggested_template=companion_templates.select(
                            owner, self.companion_templates
                        ),
                    )
                )
            return dict(
                enabled=enabled,
                status=status,
                companions=rows,
                draft_scope=hashlib.sha256(
                    (self.salt + ":companion-dashboard").encode()
                ).hexdigest()[:24],
                applied_enabled=(
                    hello.get("companion_enabled") == 1
                    if online and supported
                    else None
                ),
            )

    def save_companion_enabled(self, body):
        if (
            not isinstance(body, dict)
            or set(body) != {"enabled"}
            or type(body["enabled"]) is not bool
        ):
            raise ValueError("Choose whether companion AI is enabled")
        with self.lock:
            saved = dict(self.companion_admin, enabled=body["enabled"])
            self.set_setting("companion_admin", saved)
            changed = self.companions_enabled() != body["enabled"]
            self.companion_admin = saved
            if changed:
                # Invalidate old model results and game preference caches. Native
                # errands observe this generation change and yield to stock control.
                self.companion_generation = secrets.token_hex(12)
                self.companion_pending.clear()
                self.companion_visits.clear()
                self.companion_config_sent = 0
            return self.companion_dashboard()

    def save_companion_profile(self, body):
        if (
            not isinstance(body, dict)
            or set(body) != {"npc", "revision", "profile"}
            or not is_companion(body.get("npc"))
        ):
            raise ValueError("Choose an existing companion profile")
        values = companion_templates.validate_profile(body["profile"])
        with self.lock:
            old = self.store.get(body["npc"])
            if body["revision"] != revision(old):
                raise ValueError(
                    "This companion profile changed elsewhere. Reload the saved profile and review your edits before saving."
                )
            self.save_profile(dict(old, **values))
            return self.companion_dashboard()

    def companion_template_dashboard(self):
        with self.lock:
            return dict(
                templates=companion_templates.dashboard(self.companion_templates),
                draft_scope=hashlib.sha256(
                    (self.salt + ":companion-templates").encode()
                ).hexdigest()[:24],
            )

    def save_companion_template(self, body):
        if (
            not isinstance(body, dict)
            or set(body) != {"id", "revision", "profile", "blueprints"}
            or not isinstance(body.get("id"), str)
            or body["id"] not in companion_templates.LABELS
        ):
            raise ValueError("Choose a familiar template")
        with self.lock:
            key = body["id"]
            if body["revision"] != companion_templates.revision(
                self.companion_templates[key]
            ):
                raise ValueError(
                    "This template changed elsewhere. Reload the saved template and review your edits before saving."
                )
            value = dict(profile=body["profile"], blueprints=body["blueprints"])
            saved = companion_templates.settings(
                dict(self.companion_templates, **{key: value})
            )
            self.set_setting("companion_templates", saved)
            self.companion_templates = saved
            # Existing profiles, in-flight conversations and game permissions are
            # independent copies. A template edit must not change any of them.
            return self.companion_template_dashboard()
