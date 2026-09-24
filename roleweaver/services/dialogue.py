"""NPC response generation, wait feedback, and safeguard review.

Mixin methods run on Service and share its lock, store, state, and command queue.
They do not own separate worker pools or database connections.
"""

import time
from .. import provider, guardrails, safeguards, actions, merchants, story


class DialogueService:
    """NPC response generation, wait feedback, and safeguard review."""

    def waiting_valid(self, npc, item):
        state = self.states.get(npc, {})
        return (
            item["generation"] == self.generations.get(npc, 0)
            and state.get("mode") == "auto"
            and state.get("session") == item["session"]
            and state.get("epoch") == item["epoch"]
        )

    def thinking_tick(self):
        with self.lock:
            now = time.monotonic()
            for npc, item in list(self.waiting_replies.items()):
                if not self.waiting_valid(npc, item):
                    self.waiting_replies.pop(npc, None)
                    continue
                if now < item["next"]:
                    continue
                text = "*They pause to think.*" if item["first"] else "Hmm..."
                delay = 10
                item.update(first=False, next=now + delay)
                try:
                    self.command(
                        npc,
                        "say",
                        text=text,
                        player=item["player"],
                        listener=item["listener"],
                        transient=True,
                    )
                except Exception:
                    pass  # Feedback must not interrupt the actual reply.

    def generate(
        self,
        npc,
        player,
        profile,
        generation,
        started,
        listener,
        display_name="",
        blocked=False,
        speech=None,
        speech_id=None,
        merchant_quote=None,
    ):
        waiting = dict(
            generation=generation,
            session=started.get("session"),
            epoch=started.get("epoch"),
            player=player,
            listener=listener,
            first=True,
            next=time.monotonic() + 5,
        )
        with self.lock:
            self.waiting_replies[npc] = waiting
        try:
            action_choice = ""
            price_stamp = ""
            with self.lock:
                request_config = dict(self.config)
                story_context = story.context(profile.get("story"))
                profile = dict(profile, story=story_context)
                state = self.states.get(npc, {})
                profile["surroundings"] = (
                    state.get("surroundings", [])
                    if time.monotonic() - state.get("seen", 0) < 4
                    else []
                )
                profile["duty"] = (
                    self.action_config["npcs"].get(npc, {}).get("patrol", {})
                )
                available_actions = self.action_choices(npc) + story_context.get(
                    "actions", []
                )
                policy = safeguards.settings(self.safeguard_policy)
                if self.action_config["npcs"].get(npc, {}).get("shop"):
                    shop = self.shop_context(npc)
                    if (
                        shop["available"]
                        and isinstance(merchant_quote, dict)
                        and merchant_quote.get("world") == self.config["world_id"]
                        and merchant_quote.get("session") == started.get("session")
                        and merchant_quote.get("npc") == npc
                        and merchant_quote.get("listener") == listener
                        and merchant_quote.get("status") == "ready"
                        and merchant_quote.get("rules_revision")
                        == self.merchant_entry(npc)["revision"]
                        and merchant_quote.get("stock_revision")
                        == self.shop_states.get(npc, {}).get("stock_revision")
                        and isinstance(merchant_quote.get("price_stamp"), str)
                        and merchant_quote["price_stamp"]
                    ):
                        shop = dict(
                            shop,
                            items=merchant_quote.get("items", []),
                            haggle=merchant_quote.get("haggle", {}),
                            customer_quote=True,
                        )
                    profile = dict(profile, merchant=shop)
            history = provider.private_transcript(
                self.store.transcript(npc, player, 16),
                display_name,
                self.name_privacy_cutoff,
            )
            history = story.mark_history(history, profile.get("story_first_message"))
            if speech is None:
                speech = next(
                    (r["text"] for r in reversed(history) if r["speaker"] == "player"),
                    "",
                )
            speech = safeguards.scrub(speech, policy)[0]
            profile = safeguards.scrub_tree(profile, policy)
            memories = safeguards.scrub_tree(self.store.memories(npc, player), policy)
            history = safeguards.scrub_tree(history, policy)
            input_reason = self.validation.check(speech, "input")
            decision = "allow"
            if not blocked and not input_reason:
                decision = self.review_dialogue(
                    npc, speech, "input", policy, {}, request_config
                )
            if decision in ("fallback", "block") and speech_id is not None:
                # Rejected dialogue must not be replayed on the next turn.
                with self.store.lock, self.store.db:
                    self.store.db.execute(
                        "UPDATE messages SET text=? WHERE id=?",
                        ("[Dialogue withheld by server safeguards.]", speech_id),
                    )
            if decision == "block":
                return
            if blocked or input_reason or decision == "fallback":
                text = guardrails.FALLBACK
                if blocked or input_reason:
                    self.safeguard_event(npc, "input", ["core_protection"], "fallback")
                with self.lock:
                    self.guard_counts["input_blocked"] += 1
                    self.diagnostics.setdefault(npc, {})["error"] = (
                        input_reason or "Dialogue declined by server safeguards."
                    )
            else:
                # Validate older dialogue too, so old attacks cannot be replayed.
                if self.validation.enabled:
                    checked = []
                    for row in history:
                        reason = self.validation.check(
                            row["text"],
                            "input" if row["speaker"] == "player" else "output",
                            profile,
                        )
                        if self.validation.error:
                            raise RuntimeError("Dialogue validation unavailable")
                        checked.append(
                            dict(
                                row,
                                text=(
                                    "[An out-of-character request was declined.]"
                                    if row["speaker"] == "player"
                                    else guardrails.FALLBACK
                                ),
                            )
                            if reason
                            else row
                        )
                    history = checked
                if available_actions and request_config.get("provider") != "offline":
                    profile["controlled_actions"] = available_actions
                with provider.observe_requests(
                    self.usage.recorder(npc, "dialogue", request_config)
                ):
                    text = provider.reply(
                        request_config,
                        profile,
                        memories,
                        guardrails.clean_history(history),
                    )
                if profile.get("controlled_actions"):
                    text, action_choice = actions.parse_reply(text, available_actions)
                if profile.get("merchant"):
                    text, quoted = merchants.price_reply(
                        text, speech, profile["merchant"], action_choice
                    )
                    if quoted:
                        price_stamp = merchant_quote["price_stamp"]
                text, masked = safeguards.scrub(text, policy)
                if masked:
                    self.safeguard_event(npc, "output", masked, "masked")
                text = provider.game_speech(text)
                reason = self.validation.check(text, "output", profile)
                if reason:
                    action_choice = ""
                    text = guardrails.FALLBACK
                    self.safeguard_event(npc, "output", ["core_protection"], "fallback")
                    with self.lock:
                        self.guard_counts["replies_replaced"] += 1
                        self.diagnostics.setdefault(npc, {})["error"] = reason
                else:
                    sources = (
                        safeguards.trusted_sources(profile, memories)
                        if policy["lore_check"]
                        else {}
                    )
                    decision = self.review_dialogue(
                        npc, text, "output", policy, sources, request_config
                    )
                    if decision == "block":
                        return
                    if decision == "fallback":
                        action_choice = ""
                        text = "I cannot speak with certainty about that. Ask me about something else."
                        with self.lock:
                            self.guard_counts["replies_replaced"] += 1

            with self.lock:
                state = self.states.get(npc, {})
                if (
                    generation != self.generations.get(npc, 0)
                    or state.get("mode") != "auto"
                ):
                    return
                if (
                    state.get("session") != started["session"]
                    or state.get("epoch") != started["epoch"]
                ):
                    return
                self.waiting_replies.pop(npc, None)
                if not text.strip():
                    raise ValueError("Empty NPC response")
                self.command(
                    npc,
                    "say",
                    text=text,
                    player=player,
                    listener=listener,
                    action_choice=(
                        "" if action_choice.startswith("story:") else action_choice
                    ),
                    story_action=(
                        action_choice if action_choice.startswith("story:") else ""
                    ),
                    story_token=story_context.get("token", ""),
                    action_generation=generation,
                    price_stamp=price_stamp,
                )
                self.last_reply[npc] = time.monotonic()
        except Exception as exc:
            with self.lock:
                self.diagnostics.setdefault(npc, {})["error"] = (
                    "Reply failed: "
                    + type(exc).__name__
                    + ". Check provider settings and connection."
                )
                self.waiting_replies.pop(npc, None)
                if self.waiting_valid(npc, waiting):
                    try:
                        self.command(
                            npc,
                            "say",
                            text="*They seem to have nothing useful to add.*",
                            player=player,
                            listener=listener,
                            transient=True,
                        )
                    except Exception:
                        pass
        finally:
            with self.lock:
                self.waiting_replies.pop(npc, None)
                self.busy.discard(npc)

    def safeguard_event(self, npc, stage, categories, action):
        # Deliberately retain no dialogue, source excerpts, account IDs or PII.
        with self.store.lock, self.store.db:
            self.store.db.execute(
                "INSERT INTO safeguard_events(created,npc,stage,categories,action) VALUES (?,?,?,?,?)",
                (time.time(), npc, stage, ", ".join(categories), action),
            )
            self.store.db.execute(
                "DELETE FROM safeguard_events WHERE id NOT IN (SELECT id FROM safeguard_events ORDER BY id DESC LIMIT 200)"
            )

    def safeguard_status(self):
        with self.lock, self.store.lock:
            return {
                "settings": safeguards.settings(self.safeguard_policy),
                "sdk": self.validation.status(),
                "provider_ready": self.config.get("provider") == "openai-compatible",
                "events": [
                    dict(r)
                    for r in self.store.db.execute(
                        "SELECT created,npc,stage,categories,action FROM safeguard_events ORDER BY id DESC LIMIT 20"
                    )
                ],
            }

    def save_safeguards(self, value):
        if not isinstance(value, dict):
            raise ValueError("Supply safeguard settings as an object")
        policy = safeguards.settings(value)
        if (
            safeguards.needs_review(policy, "input") or policy["lore_check"]
        ) and self.config.get("provider") != "openai-compatible":
            raise ValueError(
                "AI content and lore checks require an online provider. Local privacy masking remains available."
            )
        with self.lock:
            if self.restoring:
                raise ValueError("Wait for restore to finish")
            self.set_setting("safeguards", policy)
            self.safeguard_policy = policy
            for npc in self.busy:
                self.generations[npc] = self.generations.get(npc, 0) + 1
        return self.safeguard_status()

    def review_dialogue(
        self, npc, text, direction, policy, sources, request_config=None
    ):
        request_config = request_config or dict(self.config)
        if not safeguards.needs_review(policy, direction):
            return "allow"
        try:
            with provider.observe_requests(
                self.usage.recorder(npc, direction + "_review", request_config)
            ):
                report = provider.review(
                    request_config, text, direction, policy, sources
                )
            found = safeguards.flags(report, policy, direction)
            if self.validation.enabled:
                if self.validation.backend is None:
                    raise RuntimeError("Guardrails AI unavailable")
                passed = self.validation.backend.review_passed(
                    report, policy, direction
                )
                if passed != (not found):
                    raise RuntimeError("Inconsistent policy validation")
        except Exception:
            self.safeguard_event(npc, direction, ["review_unavailable"], "block")
            with self.lock:
                self.diagnostics.setdefault(npc, {})[
                    "error"
                ] = "AI safeguard review unavailable; reply blocked. Check provider and source size."
            return "block"
        if not found:
            return "allow"
        action = policy["action"]
        self.safeguard_event(npc, direction, found, action)
        with self.lock:
            self.diagnostics.setdefault(npc, {})["error"] = (
                "Safeguards: " + ", ".join(found) + " (" + action + ")."
            )
        return "allow" if action == "log" else action
