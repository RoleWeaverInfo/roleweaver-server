"""Validate merchant configuration and stock editing requests."""

import secrets
import time
from . import merchants, actions


class MerchantAdmin:
    def merchant_entry(self, npc):
        return self.merchant_config.get(
            npc, dict(rules=dict(merchants.DEFAULT_RULES), revision="defaults-v2")
        )

    def merchant_status(self):
        with self.lock:
            rows = []
            for p in self.store.list_npcs():
                if not self.action_config["npcs"].get(p["id"], {}).get("shop"):
                    continue
                npc = p["id"]
                entry = self.merchant_entry(npc)
                stock = self.shop_states.get(npc, {})
                job = dict(self.merchant_jobs.get(npc, {}))
                if (
                    job.get("status") == "pending"
                    and time.monotonic() - job["started"] > 15
                ):
                    job.update(
                        status="unknown",
                        message="Confirmation timed out. Refresh stock before deciding whether to retry; edits are not replayed automatically.",
                    )
                job.pop("started", None)
                job.pop("session", None)
                fresh = (
                    stock.get("session") == self.states.get(npc, {}).get("session")
                    and time.monotonic() - stock.get("seen", 0) < 8
                )
                active = bool(self.action_config["npcs"][npc]["enabled"])
                state = self.states.get(npc, {})
                editable = bool(
                    active
                    and not state.get("possessed")
                    and not state.get("dead")
                    and not state.get("combat")
                    and self.shop_context(npc)["available"]
                )
                rows.append(
                    dict(
                        enabled=active,
                        editable=editable,
                        id=npc,
                        name=p["name"],
                        rules=entry["rules"],
                        revision=entry["revision"],
                        applied=fresh
                        and stock.get("rules_revision") == entry["revision"],
                        stock=stock if fresh else {},
                        fresh=fresh,
                        job=job,
                    )
                )
            return dict(
                merchants=rows,
                catalog=merchants.CATALOG,
                ready=self.action_status()["ready"],
            )

    def save_merchant_rules(self, npc, value, revision):
        self.store.get(npc)
        if not self.action_config["npcs"].get(npc, {}).get("shop"):
            raise ValueError("Enable this NPC’s shop under Controlled Actions first")
        if revision != self.merchant_entry(npc)["revision"]:
            raise ValueError(
                "Settings changed in another window. Reload before saving."
            )
        clean = merchants.rules(value)
        if clean != self.merchant_entry(npc)["rules"]:
            self.merchant_config[npc] = dict(
                rules=clean, revision=secrets.token_hex(12)
            )
            self.set_setting("merchant_configs", self.merchant_config)
            self.generations[npc] = self.generations.get(npc, 0) + 1
            self.shop_sent.pop(npc, None)
        return self.merchant_status()

    def edit_merchant_stock(self, npc, operation, revision, item="", quantity=1):
        self.store.get(npc)
        stock = self.shop_states.get(npc, {})
        if (
            not self.shop_context(npc)["available"]
            or stock.get("rules_revision") != self.merchant_entry(npc)["revision"]
        ):
            raise ValueError(
                "Wait for this merchant’s game connection and settings confirmation"
            )
        state = self.states.get(npc, {})
        if state.get("possessed") or state.get("dead") or state.get("combat"):
            raise ValueError(
                "Stock cannot be edited during possession, death or combat"
            )
        if not isinstance(revision, str) or revision != stock.get("stock_revision"):
            raise ValueError("Stock changed. Refresh and select the item again.")
        job = self.merchant_jobs.get(npc, {})
        if (
            job.get("status") == "pending"
            and time.monotonic() - job.get("started", 0) < 15
        ):
            raise ValueError("A stock edit is awaiting game confirmation")
        if operation == "add":
            if (
                item not in {r["id"] for r in merchants.CATALOG}
                or type(quantity) is not int
                or not 1 <= quantity <= 20
            ):
                raise ValueError("Choose a catalogue item and quantity from 1 to 20")
        elif operation == "remove":
            if type(quantity) is not int or not any(
                r.get("item") == item and r.get("quantity") == quantity
                for r in stock.get("items", [])
            ):
                raise ValueError("Select a current stock row to remove")
        else:
            raise ValueError("Unknown stock operation")
        request = self.command(
            npc,
            "merchant_stock_edit",
            world=self.config["world_id"],
            operation=operation,
            item=item,
            quantity=quantity,
            stock_revision=revision,
            rules_revision=self.merchant_entry(npc)["revision"],
        )
        self.generations[npc] = self.generations.get(npc, 0) + 1
        self.merchant_jobs[npc] = dict(
            request=request,
            session=state["session"],
            started=time.monotonic(),
            status="pending",
            message="Waiting for the game to save and confirm the stock edit.",
        )
        return self.merchant_status()

    def merchant_ack(self, pending, event):
        npc = pending["npc"]
        job = self.merchant_jobs.get(npc, {})
        if job.get("request") != event.get("request") or job.get(
            "session"
        ) != event.get("session"):
            return
        job.update(
            status="confirmed" if event.get("ok") == 1 else "rejected",
            message=(
                "Stock saved. Customers must reopen the shop; previous offers are invalidated."
                if event.get("ok") == 1
                else "Game rejected the edit. Refresh stock and check NPC state; no automatic retry was made."
            ),
        )
