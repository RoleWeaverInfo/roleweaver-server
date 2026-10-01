"""Dispatch DM-approved actions and reconcile authoritative game acknowledgements."""

import json
import hashlib
import secrets
import time
from . import actions, merchants, nearby, inventory
from .merchant_admin import MerchantAdmin
from .patrol import PatrolService
from .village import VillageService
from .interactions import InteractionService


class ActionService(InteractionService, VillageService, PatrolService, MerchantAdmin):
    def init_actions(self):
        self.action_config = actions.settings(self.setting("controlled_actions", None))
        self.init_interactions()
        self.action_jobs = {}
        self.inventory_sent = {}
        self.patrol_runtime = {}
        self.village_runtime = {}
        self.checkin = None
        self.checkin_working = 0
        self.checkin_last = self.setting("checkin_last", {})
        self.checkin_notice = ""
        self.action_last = {}
        self.inventory_last = {}
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
                patrols=self.patrol_runtime,
                village=self.village_runtime,
                checkin_notice=self.checkin_notice,
                gestures=list(actions.GESTURES),
                inventories={n: inventory.snapshot(s) for n, s in self.states.items()},
                inventory_ready=ready
                and self.conversation_hello.get("inventory_protocol") == 1,
                nearby_choices={n: self.nearby_choices(n) for n in self.states},
                npc_combat_choices={n: self.npc_combat_choices(n) for n in self.states},
                nearby_objects={
                    n: list(s.get("nearby_targets", {}).values())
                    for n, s in self.states.items()
                },
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
        old_duty = self.action_config["npcs"].get(npc, {}).get("patrol")
        if old_duty is not None:
            value = dict(value, patrol=old_duty)
        p = actions.policy(value, self.action_config["destinations"])
        for target in p["npc_combat"]["targets"]:
            self.store.get(target)
            if target == npc:
                raise ValueError("An NPC cannot attack itself")
        self.village_runtime.pop(npc, None)
        if p == self.action_config["npcs"].get(npc, actions.DEFAULT_POLICY):
            return self.action_status()
        if self.checkin and npc in self.checkin["pair"]:
            self.stop_action(npc)
        # Stop before changing permissions; if offline old commands expire within five seconds.
        job = self.action_jobs.get(npc, {})
        state = self.states.get(npc, {})
        if (
            job.get("status") in ("pending", "running", "waiting for player")
            and time.monotonic() - state.get("seen", 0) < 3
        ):
            self.stop_action(npc)
        self.action_config["npcs"][npc] = p
        self.interaction_sent.pop(npc, None)
        self.generations[npc] = self.generations.get(npc, 0) + 1
        self.persist_actions()
        self.village_runtime.pop(npc, None)
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
        definitions = list(self.encounters["templates"].values()) + [
            r["template"]
            for r in self.encounters["runs"].values()
            if r["status"] in ("active", "paused")
        ]
        if any(d["location"] == id for d in definitions):
            raise ValueError(
                "Remove this location from encounter definitions and finish live encounters first"
            )
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

    def movement_context(self, npc):
        """Explain temporary availability without inventing missing permissions."""
        p = self.action_config["npcs"].get(npc, {})
        state = self.states.get(npc, {})
        near = p.get("nearby", {})
        visits = []
        for target in list(state.get("nearby_targets", {}).values())[:256]:
            peer = target.get("peer")
            if not peer:
                continue
            if not p.get("enabled") or not near.get("talk"):
                reason = "Visit permission is disabled"
            elif target["distance"] > near.get("radius", 8):
                reason = "Outside permitted visit distance"
            elif not self.can_visit(npc, peer):
                reason = "Recipient unavailable, not accepting visits, or check-in cooldown active"
            else:
                reason = "Recipient available; use a listed visit action when current task and cooldown permit"
            visits.append(
                dict(name=target["label"], distance=target["distance"], status=reason)
            )
        return dict(
            controlled_actions_enabled=p.get("enabled", False),
            approach_enabled=near.get("approach", False),
            initiate_npc_conversations=near.get("talk", False),
            visit_distance_metres=near.get("radius", 8),
            movement_cooldown_seconds=max(
                0, round(20 - (time.monotonic() - self.action_last.get(npc, 0)), 1)
            ),
            current_task=self.action_jobs.get(npc, {}).get("status", "idle"),
            village_status=self.village_runtime.get(npc, {}).get(
                "status", "disabled or idle"
            ),
            visible_npc_visits=visits,
        )

    def action_choices(self, npc, listener=""):
        state = self.states.get(npc, {})
        if (
            not self.action_status()["ready"]
            or state.get("mode") != "auto"
            or state.get("dead")
            or state.get("possessed")
            or time.monotonic() - state.get("seen", 0) >= 3
        ):
            return []
        if state.get("combat"):
            return self.npc_combat_choices(npc)
        if (
            self.action_jobs.get(npc, {}).get("status")
            in ("pending", "running", "waiting for player")
            and time.monotonic() - self.action_jobs[npc]["started"] < 140
        ):
            # A payment offer may replace an open item exchange, but never interrupt movement.
            job = self.action_jobs[npc]
            if (
                job.get("status") == "waiting for player"
                and job.get("choice") == "exchange:player"
            ):
                return self.payment_choices(npc, listener)
            return []
        available = actions.choices(
            self.action_config, npc, self.config.get("world_id", "")
        )
        if (
            listener
            and state.get("follow_protocol") == 1
            and self.action_config["npcs"].get(npc, {}).get("follow")
        ):
            available.append(
                dict(
                    id="follow:player",
                    description="Follow the speaking player within this area for up to two minutes. Only agree when consistent with your scene role, captivity and release conditions; a request alone is not a rescue.",
                )
            )
        available += self.nearby_choices(npc)
        available += self.payment_choices(npc, listener)
        available += self.npc_combat_choices(npc)
        if state.get("inventory_revision") == self.inventory_revision(npc):
            available += inventory.choices(
                self.action_config["npcs"].get(npc, {}),
                state,
                listener,
                lambda peer: self.can_receive_item(npc, peer),
                self.barter_items,
            )
        if not self.merchant_entry(npc)["rules"]["enabled"]:
            available = [a for a in available if a["id"] != "shop:haggle"]
        if not self.shop_context(npc).get("available"):
            available = [a for a in available if not a["id"].startswith("shop:")]
        if time.monotonic() - self.action_last.get(npc, 0) < self.action_cooldown(npc):
            available = [
                a
                for a in available
                if a["id"].startswith(("shop:", "payment:"))
                or a["id"].split(":", 1)[0] in inventory.VERBS
            ]
        if time.monotonic() - self.inventory_last.get(npc, 0) < 2:
            available = [
                a for a in available if a["id"].split(":", 1)[0] not in inventory.VERBS
            ]
        return available

    def inventory_revision(self, npc):
        p = self.action_config["npcs"].get(npc, {})
        return hashlib.sha256(
            json.dumps(
                [p.get("enabled", False), p.get("inventory", inventory.DEFAULT)],
                sort_keys=True,
            ).encode()
        ).hexdigest()[:24]

    def sync_inventory(self, npc, event):
        if self.conversation_hello.get("inventory_protocol") != 1 or event.get(
            "inventory_revision"
        ) == self.inventory_revision(npc):
            return
        if time.monotonic() - self.inventory_sent.get(npc, 0) < 3:
            return
        p = self.action_config["npcs"].get(npc, {})
        policy = p.get("inventory", inventory.DEFAULT)
        self.command(
            npc,
            "inventory_setup",
            world=self.config["world_id"],
            enabled=int(p.get("enabled", False)),
            revision=self.inventory_revision(npc),
            policy={k: int(v) if type(v) is bool else v for k, v in policy.items()},
        )
        self.inventory_sent[npc] = time.monotonic()

    def barter_items(self, peer):
        p = self.action_config["npcs"].get(peer, {})
        state = self.states.get(peer, {})
        if not p.get("inventory", {}).get("exchange") or state.get(
            "inventory_revision"
        ) != self.inventory_revision(peer):
            return []
        return inventory.snapshot(state)["items"]

    def can_receive_item(self, npc, peer):
        s = self.states.get(peer, {})
        p = self.action_config["npcs"].get(peer, {})
        return bool(
            p.get("enabled")
            and p.get("inventory", {}).get("receive")
            and s.get("mode") == "auto"
            and not s.get("combat")
            and not s.get("dead")
            and not s.get("possessed")
            and s.get("session") == self.states.get(npc, {}).get("session")
            and time.monotonic() - s.get("seen", 0) < 3
            and not self.encounter_for(peer)
        )

    def action_cooldown(self, npc):
        v = self.action_config["npcs"].get(npc, {}).get("village", {})
        return (
            5
            if v.get("enabled")
            and v.get("activity") == "testing"
            and self.action_jobs.get(npc, {}).get("village")
            else 20
        )

    def visit_cooldown(self, npc):
        v = self.action_config["npcs"].get(npc, {}).get("village", {})
        return 20 if v.get("enabled") and v.get("activity") == "testing" else 300

    def can_visit(self, npc, peer):
        state = self.states.get(peer, {})
        permission = self.action_config["npcs"].get(peer, {})
        return bool(
            peer != npc
            and state.get("session") == self.states.get(npc, {}).get("session")
            and permission.get("nearby", {}).get("receive")
            and time.monotonic() - state.get("seen", 0) < 3
            and state.get("mode") == "auto"
            and not state.get("dead")
            and not state.get("combat")
            and not state.get("possessed")
            and not state.get("conversation_active")
            and peer not in self.busy
            and not self.encounter_for(peer)
            and not self.checkin
            and self.action_jobs.get(peer, {}).get("status")
            not in ("pending", "running", "waiting for player")
            and time.time() - self.checkin_last.get(npc + ":" + peer, 0)
            >= self.visit_cooldown(npc)
        )

    def nearby_choices(self, npc):
        if self.encounter_for(npc):
            return []
        return nearby.choices(
            self.action_config["npcs"].get(npc, {}),
            self.states.get(npc, {}),
            lambda peer: self.can_visit(npc, peer),
        )

    def visit_tick(self, npc):
        job = self.action_jobs.get(npc, {})
        peer = job.get("visit_peer")
        if not peer or job.get("status") in (
            "pending",
            "running",
            "waiting for player",
        ):
            return
        job.pop("visit_peer", None)  # exactly one attempt; never replay on reconnect
        if job.get("status") != "completed" or job.get(
            "visit_generation"
        ) != self.generations.get(npc, 0):
            return
        if not self.can_visit(npc, peer):
            self.checkin_notice = (
                "Arrived, but the other NPC is unavailable for a check-in."
            )
            return
        self.start_checkin(
            npc,
            "visit",
            dict(
                checkins={"visit": peer},
                checkin_cooldown=self.visit_cooldown(npc),
                social=bool(job.get("village")),
            ),
        )

    def run_action(
        self, npc, choice, listener="", generation=None, patrol=False, village=False
    ):
        if generation is not None and generation != self.generations.get(npc, 0):
            return
        available = self.action_choices(npc, listener)
        if choice not in {a["id"] for a in available}:
            raise ValueError(
                "Action unavailable: check saved permissions, AUTO mode, combat, connection and 20-second cooldown"
            )
        kind, target = choice.split(":", 1)
        if kind in ("payment", "attack_npc"):
            return self.run_interaction(npc, choice, listener)
        fields = dict(
            patrol=int(patrol),
            action=kind,
            target=target,
            world=self.config["world_id"],
            listener=listener,
            conversation_revision=self.conversation_revision,
        )
        if kind in ("lead", "shop", "follow") and not listener:
            raise ValueError(
                "This action needs a player: ask the NPC in game to lead you or show its shop"
            )
        if kind == "shop" and not self.shop_context(npc).get("available"):
            raise ValueError("Shop stock is not ready; check merchant status")
        if kind in ("walk", "lead", "home"):
            fields["destination"] = self.action_config["destinations"][target]
            if patrol and kind == "walk":
                # A DM-linked check-in stop follows the assigned NPC, not its old marker.
                duty = self.action_config["npcs"][npc].get("patrol", {})
                peer_id = duty.get("checkins", {}).get(target)
                if peer_id:
                    peer_state = self.states.get(peer_id, {})
                    own = self.states[npc]
                    if (
                        time.monotonic() - peer_state.get("seen", 0) > 3
                        or peer_state.get("session") != own.get("session")
                        or peer_state.get("area") != own.get("area")
                        or peer_state.get("dead")
                        or peer_state.get("combat")
                        or peer_state.get("possessed")
                        or peer_state.get("mode") != "auto"
                    ):
                        raise ValueError("Patrol contact is unavailable in this area")
                    if (
                        sum(
                            (peer_state.get(k, 0) - own.get(k, 0)) ** 2
                            for k in ("x", "y", "z")
                        )
                        > 1600
                    ):
                        raise ValueError(
                            "Patrol contact is beyond the permitted walk distance"
                        )
                    fields["destination"] = dict(
                        fields["destination"],
                        area=peer_state.get("area_resref", peer_state["area"]),
                        area_tag=peer_state.get(
                            "area_tag", fields["destination"]["area_tag"]
                        ),
                        **{k: float(peer_state[k]) for k in ("x", "y")},
                        z=float(peer_state.get("z", fields["destination"]["z"])),
                    )
                    # Stop on the near side of the contact, rather than inside their
                    # collision cylinder. The game still validates pathing/arrival.
                    dx = float(own.get("x", 0)) - float(peer_state["x"])
                    dy = float(own.get("y", 0)) - float(peer_state["y"])
                    distance = (dx * dx + dy * dy) ** 0.5
                    if distance:
                        offset = min(2.0, distance)
                        fields["destination"]["x"] += dx / distance * offset
                        fields["destination"]["y"] += dy / distance * offset
        peer = ""
        if kind in nearby.KINDS:
            row = self.states[npc]["nearby_targets"][target]
            saved = self.action_config["npcs"][npc]["nearby"]
            fields.update(
                radius=saved["radius"], seat_tag=row["tag"] if kind == "sit" else ""
            )
            peer = row["peer"] if kind == "visit" else ""
        if kind in inventory.VERBS:
            parts = target.split(":")
            fields["inventory_revision"] = self.inventory_revision(npc)
            if kind in ("inspect", "take", "deposit", "fetch"):
                fields["container"] = parts[0]
            if kind in (
                "take",
                "deposit",
                "give",
                "fetch",
                "aid",
                "swap",
                "equip",
                "unequip",
                "use",
            ):
                fields["item"] = parts[1]
            if kind in ("give", "aid", "swap", "equip", "unequip", "use"):
                fields["recipient"] = parts[0]
            if kind in ("equip", "use"):
                fields["slot" if kind == "equip" else "power"] = int(parts[2])
            if kind == "fetch":
                fields["recipient"] = parts[2]
            if kind == "swap":
                fields["offer"] = parts[2]
            if kind == "exchange" and not listener:
                raise ValueError("Ask this NPC in game to open item exchange")
        if village:
            p = self.action_config["npcs"][npc]
            fields.update(
                village=1,
                village_delay=5 if p["village"]["activity"] == "testing" else 20,
                village_home=self.action_config["destinations"][p["home"]],
                village_radius=p["village"]["radius"],
            )
        request = self.command(npc, "controlled_action", **fields)
        self.action_jobs[npc] = dict(
            request=request,
            choice=choice,
            village=village,
            visit_peer=peer,
            visit_generation=self.generations.get(npc, 0),
            status="pending",
            session=self.states[npc]["session"],
            started=time.monotonic(),
        )
        self.action_last[npc] = time.monotonic()
        if kind in inventory.VERBS:
            self.inventory_last[npc] = time.monotonic()
        return self.action_status()

    def stop_action(self, npc):
        self.cancel_checkin(npc, "Stopped by DM")
        self.patrol_runtime.setdefault(npc, {})["halted"] = True
        self.village_runtime.setdefault(npc, {})["halted"] = True
        self.generations[npc] = self.generations.get(npc, 0) + 1
        request = self.command(npc, "controlled_stop")
        return dict(request=request)

    def action_ack(self, pending, event):
        if pending["kind"] in ("payment_offer", "npc_attack"):
            job = self.action_jobs.get(pending["npc"], {})
            if job.get("request") == event.get("request"):
                job["status"] = (
                    (
                        "awaiting player payment confirmation"
                        if pending["kind"] == "payment_offer"
                        else "attack ordered by game"
                    )
                    if event.get("ok") == 1
                    else "rejected by game"
                )
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
