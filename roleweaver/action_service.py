"""Dispatch DM-approved actions and reconcile authoritative game acknowledgements."""

import json
import secrets
import time
from . import actions, merchants
from .merchant_admin import MerchantAdmin


class ActionService(MerchantAdmin):
    def init_actions(self):
        self.action_config = actions.settings(self.setting("controlled_actions", None))
        self.action_jobs = {}
        self.action_last = {}
        self.action_notice = ""
        self.shop_states = {}
        self.shop_sent = {}
        self.merchant_config = merchants.configs(self.setting("merchant_configs", None))
        self.merchant_jobs = {}

    def action_status(self):
        with self.lock:
            hello = self.conversation_hello
            ready = (
                time.monotonic() - hello.get("seen", 0) < 4
                and hello.get("actions_protocol") == 6
            )
            jobs = {}
            for npc, job in self.action_jobs.items():
                item = dict(job)
                state = self.states.get(npc, {})
                if item["status"] in ("pending", "running", "waiting for player") and (
                    time.monotonic() - state.get("seen", 0) > 4
                    or state.get("session") != item["session"]
                ):
                    item["status"] = "connection lost; outcome unknown"
                elif (
                    item["status"] in ("pending", "running", "waiting for player")
                    and time.monotonic() - item["started"] > 140
                ):
                    item["status"] = "confirmation timed out"
                jobs[npc] = {
                    k: v for k, v in item.items() if k not in ("started", "session")
                }
            return dict(
                config=self.action_config,
                jobs=jobs,
                ready=ready,
                notice=self.action_notice,
                gestures=list(actions.GESTURES),
                shops={
                    k: dict(v, stale=time.monotonic() - v.get("seen", 0) > 8)
                    for k, v in self.shop_states.items()
                },
            )

    def persist_actions(self):
        self.action_config = actions.settings(self.action_config)
        self.set_setting("controlled_actions", self.action_config)

    def save_action_policy(self, npc, value):
        self.store.get(npc)
        p = actions.policy(value, self.action_config["destinations"])
        if p == self.action_config["npcs"].get(npc, actions.DEFAULT_POLICY):
            return self.action_status()
        # Stop before changing permissions; if offline old commands expire within five seconds.
        job = self.action_jobs.get(npc, {})
        state = self.states.get(npc, {})
        if (
            job.get("status") in ("pending", "running", "waiting for player")
            and time.monotonic() - state.get("seen", 0) < 3
        ):
            self.stop_action(npc)
        self.action_config["npcs"][npc] = p
        self.generations[npc] = self.generations.get(npc, 0) + 1
        self.persist_actions()
        return self.action_status()

    def capture_destination(self, id, name, dm):
        actions.identifier(id)
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError("Enter a location name (1–80 characters)")
        if id in self.action_config["destinations"]:
            raise ValueError(
                "Use a new destination ID; existing destinations cannot be moved silently"
            )
        if len(self.action_config["destinations"]) >= 100:
            raise ValueError("Maximum 100 destinations")
        if any(p["kind"] == "action_capture" for p in self.pending.values()):
            raise ValueError("A location capture is already pending")
        target = self.dms.get(dm)
        if (
            not self.action_status()["ready"]
            or not target
            or time.monotonic() - target["seen"] >= 3
        ):
            raise ValueError("Connect as an unpossessed DM on the updated game server")
        request = secrets.token_hex(12)
        self.pending[request] = dict(
            kind="action_capture",
            npc="",
            time=time.monotonic(),
            id=id,
            name=name.strip(),
            session=target["session"],
        )
        cmd = dict(
            kind="action_capture",
            world=self.config["world_id"],
            dm=dm,
            token=target["token"],
            session=target["session"],
            expires=target["tick"] + 5,
            request=request,
        )
        try:
            self.redis.call("RPUSH", self.prefix + ":commands", json.dumps(cmd))
        except Exception:
            self.pending.pop(request, None)
            raise
        self.action_notice = "Recording location; waiting for game confirmation."
        return self.action_status()

    def action_capture_event(self, event):
        with self.lock:
            pending = self.pending.get(event.get("request"))
            if (
                not pending
                or pending["kind"] != "action_capture"
                or event.get("session") != pending["session"]
                or event.get("world") != self.config["world_id"]
            ):
                return
            self.pending.pop(event["request"], None)
            if event.get("ok") != 1:
                self.action_notice = "Location rejected; connect as an unpossessed DM in a uniquely identified area."
                return
            point = actions.destination(
                dict(event, id=pending["id"], name=pending["name"])
            )
            self.action_config["destinations"][point["id"]] = point
            self.persist_actions()
            self.action_notice = (
                "Recorded "
                + point["name"]
                + ". Enable it for the NPCs allowed to walk there."
            )

    def delete_destination(self, id):
        if id not in self.action_config["destinations"]:
            raise ValueError("Unknown destination")
        if any(
            id in p["destinations"] or id in p["lead_destinations"] or id == p["home"]
            for p in self.action_config["npcs"].values()
        ):
            raise ValueError("Remove this location from NPC permissions first")
        del self.action_config["destinations"][id]
        self.persist_actions()
        return self.action_status()

    def action_choices(self, npc):
        state = self.states.get(npc, {})
        if (
            not self.action_status()["ready"]
            or state.get("mode") != "auto"
            or state.get("dead")
            or state.get("possessed")
            or state.get("combat")
            or time.monotonic() - state.get("seen", 0) >= 3
        ):
            return []
        if (
            self.action_jobs.get(npc, {}).get("status")
            in ("pending", "running", "waiting for player")
            and time.monotonic() - self.action_jobs[npc]["started"] < 140
        ):
            return []
        available = actions.choices(
            self.action_config, npc, self.config.get("world_id", "")
        )
        if not self.merchant_entry(npc)["rules"]["enabled"]:
            available = [a for a in available if a["id"] != "shop:haggle"]
        if not self.shop_context(npc).get("available"):
            available = [a for a in available if not a["id"].startswith("shop:")]
        if time.monotonic() - self.action_last.get(npc, 0) < 20:
            available = [a for a in available if a["id"].startswith("shop:")]
        return available

    def run_action(self, npc, choice, listener="", generation=None):
        if generation is not None and generation != self.generations.get(npc, 0):
            return
        available = self.action_choices(npc)
        if choice not in {a["id"] for a in available}:
            raise ValueError(
                "Action unavailable: check saved permissions, AUTO mode, combat, connection and 20-second cooldown"
            )
        kind, target = choice.split(":", 1)
        fields = dict(
            action=kind,
            target=target,
            world=self.config["world_id"],
            listener=listener,
            conversation_revision=self.conversation_revision,
        )
        if kind in ("lead", "shop") and not listener:
            raise ValueError(
                "This action needs a player: ask the NPC in game to lead you or show its shop"
            )
        if kind == "shop" and not self.shop_context(npc).get("available"):
            raise ValueError("Shop stock is not ready; check merchant status")
        if kind in ("walk", "lead", "home"):
            fields["destination"] = self.action_config["destinations"][target]
        request = self.command(npc, "controlled_action", **fields)
        self.action_jobs[npc] = dict(
            request=request,
            choice=choice,
            status="pending",
            session=self.states[npc]["session"],
            started=time.monotonic(),
        )
        self.action_last[npc] = time.monotonic()
        return self.action_status()

    def stop_action(self, npc):
        self.generations[npc] = self.generations.get(npc, 0) + 1
        request = self.command(npc, "controlled_stop")
        return dict(request=request)

    def action_ack(self, pending, event):
        if pending["kind"] == "controlled_action":
            job = self.action_jobs.get(pending["npc"], {})
            if job.get("request") == event.get("request"):
                job["status"] = (
                    "running" if event.get("ok") == 1 else "rejected by game"
                )
        elif pending["kind"] == "controlled_stop" and event.get("ok") != 1:
            self.action_notice = "Stop rejected: NPC may be possessed or disconnected. DM control takes priority."

    def action_state(self, npc, event):
        job = self.action_jobs.get(npc)
        if event.get("action_status") in ("running", "waiting for player") and (
            not job or job.get("request") != event.get("action_request")
        ):
            job = dict(
                request=event["action_request"],
                choice="Action reported by game",
                status="running",
                session=event["session"],
                started=time.monotonic(),
            )
            self.action_jobs[npc] = job
        if (
            job
            and job["session"] == event.get("session")
            and job["request"] == event.get("action_request")
        ):
            job["status"] = event.get("action_status", "unknown")

    def shop_context(self, npc):
        saved = self.action_config["npcs"].get(npc, actions.DEFAULT_POLICY)
        stock = self.shop_states.get(npc, {})
        state = self.states.get(npc, {})
        ready = (
            saved["enabled"]
            and saved["shop"]
            and stock.get("session") == state.get("session")
            and time.monotonic() - stock.get("seen", 0) < 8
            and stock.get("status") == "ready"
            and stock.get("rules_revision") == self.merchant_entry(npc)["revision"]
        )
        return dict(
            available=bool(ready),
            status=stock.get("status", "not configured"),
            items=(
                [
                    {k: v for k, v in row.items() if k != "item"}
                    for row in stock.get("items", [])
                ]
                if ready
                else []
            ),
            haggle_rules=self.merchant_entry(npc)["rules"],
            pricing="List prices are ordinary item prices. A successful haggle applies the supplied discount percentage to that price, rounded down to whole gold with a minimum price of one gold. Very cheap goods may therefore have a larger effective percentage reduction. The NWN store window is authoritative at purchase time. Stock can change while speaking. When enabled, an explicit haggle request can use shop:haggle. The game rolls d100 and succeeds when the roll is at or below haggle_rules.chance. Charisma does not affect this exact percentage chance. Success grants haggle_rules.discount percent off; failure leaves the price unchanged. The supplied cooldown applies per account/merchant, including failures. Never stack reductions. Personal prices come only from the current customer quote; never promise success. No buying items from players.",
        )

    def merchant_event(self, event):
        npc = event.get("npc", "")
        state = self.states.get(npc, {})
        if event.get("world") != self.config.get("world_id") or event.get(
            "session"
        ) != state.get("session"):
            return
        self.shop_states[npc] = dict(
            session=event["session"],
            seen=time.monotonic(),
            status=event.get("status", "unavailable"),
            items=event.get("items", [])[:100],
            rules_revision=event.get("rules_revision", ""),
            stock_revision=event.get("stock_revision", ""),
        )

    def sync_merchant(self, npc, event):
        if not self.action_status()["ready"]:
            return
        p = self.action_config["npcs"].get(npc, actions.DEFAULT_POLICY)
        enabled = bool(p["enabled"] and p["shop"])
        entry = self.merchant_entry(npc)
        if bool(event.get("merchant_enabled")) == enabled and (
            not enabled or event.get("merchant_revision") == entry["revision"]
        ):
            return
        if time.monotonic() - self.shop_sent.get(npc, 0) < 3:
            return
        self.command(
            npc,
            "merchant_setup",
            enabled=int(enabled),
            world=self.config["world_id"],
            rules=dict(entry["rules"], enabled=int(entry["rules"]["enabled"])),
            rules_revision=entry["revision"],
        )
        self.shop_sent[npc] = time.monotonic()

    def merchant_example(self):
        from .store import DEFAULT_NPC

        npc = "bram_merchant"
        if any(p["id"] == npc for p in self.store.list_npcs()):
            raise ValueError("Bram already exists; select his existing profile")
        p = dict(
            DEFAULT_NPC,
            id=npc,
            name="Bram Ironstock",
            role="Weapons merchant",
            personality="Practical, welcoming, knowledgeable about ordinary weapons. Never pressures a customer.",
            voice="Plain, friendly sentences. Brief explanations of practical weapon uses.",
            lore="You sell weapons from your assigned shop. Describe stock only from live game shop information. No established local history has been supplied.",
            boundaries="Never invent stock, prices or completed purchases. The store window handles payment and delivery. Only game-rolled haggling can change prices. No invented discounts, purchases from players, or gifts.",
            guidance="When a nearby player asks to browse or see your wares, choose the approved shop:open action if available. For an explicit bargaining request, choose shop:haggle and describe your intent without claiming success. Quote only the current customer prices supplied by the game. Offer to show the shop if uncertain.",
            mode="paused",
        )
        self.save_profile(p)
        self.save_action_policy(
            npc,
            dict(actions.DEFAULT_POLICY, enabled=True, shop=True, gestures=["greet"]),
        )
        return dict(
            npc=npc,
            message="Bram profile created. Spawn him at your DM through the NPC panel; his separate store will contain five basic weapons.",
        )
