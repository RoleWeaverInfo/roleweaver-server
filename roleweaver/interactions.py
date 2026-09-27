"""Opt-in gold requests and bounded AI-NPC combat.

Models select advertised choices. Native scripts own consent, money and combat;
receipt records are observations and never replay a transaction.
"""

import hashlib
import json
import time
from . import perception


def payment_policy(value=None):
    default = dict(enabled=False, amount=100, minimum=50, purpose="Agreed payment")
    if value is None:
        return default
    if not isinstance(value, dict) or set(value) != set(default):
        raise ValueError("Invalid payment permissions")
    if (
        type(value["enabled"]) is not bool
        or any(type(value[k]) is not int for k in ("amount", "minimum"))
        or not 1 <= value["minimum"] <= value["amount"] <= 100000
    ):
        raise ValueError(
            "Payment amounts must be 1–100000 gold; minimum cannot exceed the starting amount"
        )
    if (
        not isinstance(value["purpose"], str)
        or not 1 <= len(value["purpose"].strip()) <= 200
    ):
        raise ValueError("Describe the payment purpose (1–200 characters)")
    return dict(value, purpose=value["purpose"].strip())


def combat_policy(value=None):
    default = dict(
        enabled=False,
        allow_targeted=False,
        any_target=False,
        targets=[],
        radius=20,
        leash=20,
        retreat_hp=25,
        conditions="",
    )
    if value is None:
        return default
    if not isinstance(value, dict) or set(value) != set(default):
        raise ValueError("Invalid NPC combat permissions")
    if any(
        type(value[k]) is not bool for k in ("enabled", "allow_targeted", "any_target")
    ):
        raise ValueError("Invalid NPC combat switch")
    from .actions import identifier

    if (
        not isinstance(value["targets"], list)
        or len(value["targets"]) > 100
        or any(not isinstance(t, str) for t in value["targets"])
        or len(set(value["targets"])) != len(value["targets"])
    ):
        raise ValueError("Choose up to 100 unique NPC targets")
    for target in value["targets"]:
        identifier(target)
    for key, low, high in [("radius", 1, 40), ("leash", 2, 60), ("retreat_hp", 0, 90)]:
        if type(value[key]) is not int or not low <= value[key] <= high:
            raise ValueError("Invalid NPC combat " + key)
    if (
        not isinstance(value["conditions"], str)
        or len(value["conditions"]) > 2000
        or (value["enabled"] and not value["conditions"].strip())
    ):
        raise ValueError("Describe when this NPC may attack another NPC")
    return dict(value, targets=list(value["targets"]))


def amounts(policy):
    """A small explicit choice list; the model never supplies an unchecked price."""
    low, high = policy["minimum"], policy["amount"]
    return sorted({low + (high - low) * i // 4 for i in range(5)}, reverse=True)


class InteractionService:
    def init_interactions(self):
        self.interaction_sent = {}
        self.payment_offers = self.setting("payment_offers", {})
        self.payment_receipts = self.setting("payment_receipts", [])

    def interaction_revision(self, npc):
        p = self.action_config["npcs"].get(npc, {})
        return hashlib.sha256(
            json.dumps(
                [
                    p.get("enabled", False),
                    p.get("payment", payment_policy()),
                    p.get("npc_combat", combat_policy()),
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest()[:24]

    def sync_interactions(self, npc, event):
        if (
            event.get("interaction_protocol") != 1
            or time.monotonic() - self.interaction_sent.get(npc, 0) < 2
        ):
            return
        p = self.action_config["npcs"].get(npc, {})
        self.command(
            npc,
            "interaction_setup",
            world=self.config["world_id"],
            revision=self.interaction_revision(npc),
            enabled=bool(p.get("enabled")),
            payment=p.get("payment", payment_policy()),
            npc_combat=p.get("npc_combat", combat_policy()),
        )
        self.interaction_sent[npc] = time.monotonic()

    def interaction_ready(self, npc):
        s = self.states.get(npc, {})
        return (
            s.get("interaction_protocol") == 1
            and s.get("interaction_revision") == self.interaction_revision(npc)
            and time.monotonic() - s.get("seen", 0) < 3
        )

    def payment_choices(self, npc, listener):
        p = self.action_config["npcs"].get(npc, {})
        rule = p.get("payment", payment_policy())
        if (
            not listener
            or not p.get("enabled")
            or not rule["enabled"]
            or not self.interaction_ready(npc)
        ):
            return []
        run = self.encounter_for(npc)
        direction = self.director_npc_context(npc)
        if (
            (run and run["status"] != "active")
            or direction.get("holding")
            or direction.get("finished")
        ):
            return []
        return [
            dict(
                id="payment:" + str(n),
                description=f"Request {n} gold for {rule['purpose']}. The player must explicitly confirm in the exchange window within 3 metres. This only creates an offer; never claim payment until a receipt is confirmed.",
            )
            for n in amounts(rule)
        ]

    def npc_combat_choices(self, npc):
        p = self.action_config["npcs"].get(npc, {})
        rule = p.get("npc_combat", combat_policy())
        s = self.states.get(npc, {})
        if time.monotonic() - self.action_last.get(npc, 0) < (
            2 if s.get("combat") else self.action_cooldown(npc)
        ):
            return []
        if (
            not p.get("enabled")
            or not rule["enabled"]
            or not self.interaction_ready(npc)
            or s.get("mode") != "auto"
            or s.get("dead")
            or s.get("possessed")
            or not perception.snapshot(s)["available"]
        ):
            return []
        run = self.encounter_for(npc)
        if run and run["status"] != "active":
            return []
        direction = self.director_npc_context(npc)
        if direction.get("holding") or direction.get("finished"):
            return []
        result = []
        for row in s.get("nearby_targets", {}).values():
            peer = row.get("peer")
            other = self.states.get(peer, {})
            target = self.action_config["npcs"].get(peer, {})
            if (
                not peer
                or peer == npc
                or peer == s.get("npc_combat_target")
                or row.get("player")
                or row.get("distance", 999) > rule["radius"]
            ):
                continue
            if not rule["any_target"] and peer not in rule["targets"]:
                continue
            if (
                not target.get("enabled")
                or not target.get("npc_combat", {}).get("allow_targeted")
                or not self.interaction_ready(peer)
                or other.get("dead")
                or other.get("possessed")
                or other.get("mode") != "auto"
            ):
                continue
            other_run = self.encounter_for(peer)
            if run is not other_run:
                continue  # Never cross another encounter's reservation.
            result.append(
                dict(
                    id="attack_npc:" + peer,
                    description=f"Attack AI NPC {row['label']} only when these DM conditions are satisfied: {rule['conditions']}. This is an attack order, not proof of injury or death.",
                )
            )
        return result

    def run_interaction(self, npc, choice, listener):
        kind, target = choice.split(":", 1)
        fields = dict(
            world=self.config["world_id"], revision=self.interaction_revision(npc)
        )
        if kind == "payment":
            run = self.encounter_for(npc)
            now = time.time()
            self.payment_offers = {
                k: v for k, v in self.payment_offers.items() if now - v["created"] < 180
            }
            if len(self.payment_offers) >= 500:
                raise ValueError("Too many pending payment requests")
            # Persist offer identity before it can execute on the game thread.
            import secrets

            offer = secrets.token_hex(12)
            record = dict(
                purpose=self.action_config["npcs"][npc]["payment"]["purpose"],
                npc=npc,
                session=self.states[npc]["session"],
                epoch=self.states[npc]["epoch"],
                listener=listener,
                amount=int(target),
                created=now,
                encounter=run["template"]["id"] if run else "",
                activation=run["started"] if run else 0,
            )
            self.payment_offers[offer] = record
            self.set_setting("payment_offers", self.payment_offers)
            request = self.command(
                npc,
                "payment_offer",
                **fields,
                offer=offer,
                amount=int(target),
                listener=listener,
            )
        else:
            request = self.command(
                npc,
                "npc_attack",
                **fields,
                target=target,
                target_epoch=self.states[target]["epoch"],
                target_revision=self.interaction_revision(target),
            )
        self.action_jobs[npc] = dict(
            request=request,
            choice=choice,
            status="pending",
            session=self.states[npc]["session"],
            started=time.monotonic(),
        )
        self.action_last[npc] = time.monotonic()
        return self.action_status()

    def payment_event(self, event):
        offer = event.get("offer")
        record = self.payment_offers.get(offer)
        if (
            not record
            or event.get("world") != self.config["world_id"]
            or any(
                event.get(k) != record[k]
                for k in ("npc", "session", "epoch", "amount", "listener")
            )
            or event.get("status") != "paid"
        ):
            return
        identity = event.get("payer")
        if not isinstance(identity, str) or len(identity) > 256 or not identity:
            return
        player = hashlib.sha256((self.salt + identity).encode()).hexdigest()[:24]
        if any(r["offer"] == offer for r in self.payment_receipts):
            return
        receipt = dict(record, offer=offer, player=player, confirmed=time.time())
        self.payment_receipts = (self.payment_receipts + [receipt])[-500:]
        self.set_setting("payment_receipts", self.payment_receipts)
        run = self.encounter_for(record["npc"])
        if (
            run
            and run["template"]["id"] == record["encounter"]
            and run["started"] == record["activation"]
        ):
            self.encounter_log(
                run,
                f"Game confirmed receipt of {record['amount']} gold by {record['npc']}.",
            )
            if record["encounter"] in self.live_scenes:
                self.persist_live()
            else:
                self.persist_encounters()
        self.action_jobs[record["npc"]] = dict(
            choice="payment:" + str(record["amount"]),
            status="payment confirmed by game",
            session=record["session"],
            started=time.monotonic(),
        )

    def payment_context(self, npc, player=None):
        run = self.encounter_for(npc)
        return [
            dict(
                amount=r["amount"],
                confirmed=r["confirmed"],
                purpose=r.get("purpose", "Payment"),
            )
            for r in self.payment_receipts
            if r["npc"] == npc
            and (player is None or r["player"] == player)
            and (
                not run
                or (
                    r["encounter"] == run["template"]["id"]
                    and r["activation"] == run["started"]
                )
            )
        ][-10:]
