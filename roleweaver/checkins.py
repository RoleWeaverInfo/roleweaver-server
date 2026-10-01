"""Two-turn patrol check-ins. Only acknowledged speech enters either transcript.

One background generation at a time leaves dialogue workers for players. Both
participants are revalidated before each request and the game validates again
before speech. No NPC chat event can recursively start another conversation.
"""

import secrets
import time
from . import provider, safeguards, guardrails, perception


class CheckinService:
    def scene_exchange_valid(self, item):
        """Scene speech shares cast authority, never a player's identity or turn."""
        scene = self.director_scenes().get(item.get("scene"))
        if (
            not scene
            or scene["run"]["status"] != "active"
            or not scene.get("director", {}).get("enabled")
        ):
            return False
        run = scene["run"]
        leader = next(iter(scene["actors"]))
        if self.states.get(leader, {}).get("scene_speech_status") not in (
            "engaged",
            "negotiating",
        ):
            return False
        if run["started"] != item["activation"] or run["revision"] != item["revision"]:
            return False
        if any(n not in scene["actors"] for n in item["pair"]):
            return False
        direction = self.director_npc_context(item["pair"][0])
        presence = self.director_presence.get(item["scene"], {})
        if (
            direction.get("holding")
            or direction.get("finished")
            or not presence.get("players")
            or time.monotonic() - presence.get("seen", 0) > 12
        ):
            return False
        for n in item["pair"]:
            near = self.action_config["npcs"].get(n, {}).get("nearby", {})
            if not near.get("talk") or not near.get("receive"):
                return False
            if self.states.get(n, {}).get("scene_speech_protocol") != 1:
                return False
        return True

    def scene_exchange_tick(self):
        """At most two short exchanges per player turn, with no recursive chatter.

        First let a noncombatant speak, then another supporting actor. Fresh
        player input permits another exchange; idle scenes cannot talk forever.
        """
        if (
            self.checkin
            or self.checkin_working
            or self.restoring
            or len(self.busy) >= 3
        ):
            return
        now = time.monotonic()
        if now < getattr(self, "scene_cast_poll_at", 0):
            return
        self.scene_cast_poll_at = now + 2
        for key, scene in self.director_scenes().items():
            cast = scene["run"]["template"]["actors"]
            if len(cast) < 2 or scene["run"]["status"] != "active":
                continue
            runtime = self.director_runtime.setdefault(key, {})
            if now < runtime.get("cast_next", 0):
                continue
            with self.store.lock:
                ids = list(scene["actors"])
                latest = self.store.db.execute(
                    "SELECT COALESCE(MAX(id),0) FROM messages WHERE npc IN ("
                    + ",".join("?" for _ in ids)
                    + ") AND speaker='player' AND player NOT LIKE 'npc:%' AND created>=?",
                    (*ids, scene["run"]["started"]),
                ).fetchone()[0]
            mark = (scene["run"]["started"], latest)
            if runtime.get("cast_mark") != mark:
                runtime.update(cast_mark=mark, cast_count=0)
            if runtime.get("cast_count", 0) >= 2:
                continue
            supporting = sorted(cast[1:], key=lambda a: a.get("combatant", True))
            actor = supporting[runtime.get("cast_count", 0) % len(supporting)]["npc"]
            leader = cast[0]["npc"]
            item = dict(
                id=secrets.token_hex(12),
                pair=[actor, leader],
                turn=0,
                scene=key,
                activation=scene["run"]["started"],
                revision=scene["run"]["revision"],
                purpose="Act out your own role in the current encounter. React to your partner and the nearby visitor. A captive may plead for help; captors may answer or disagree. Reveal only your own motives and knowledge.",
                deadline=now + 90,
                stamps={},
            )
            for n in item["pair"]:
                s = self.states.get(n, {})
                item["stamps"][n] = (
                    s.get("session"),
                    s.get("epoch"),
                    self.generations.get(n, 0),
                )
            if not self.checkin_valid(item) or not self.request_budget.admit(
                "npc-checkins"
            ):
                continue
            runtime["cast_count"] = runtime.get("cast_count", 0) + 1
            runtime["cast_next"] = now + 25
            self.checkin = item
            self.checkin_working += 1
            self.pool.submit(self.generate_checkin, item)
            return

    def checkin_valid(self, item):
        if time.monotonic() > item["deadline"] or self.restoring:
            return False
        scene_exchange = bool(item.get("scene"))
        if scene_exchange and not self.scene_exchange_valid(item):
            return False
        for npc, stamp in item["stamps"].items():
            if self.encounter_for(npc) and not scene_exchange:
                return False
            s = self.states.get(npc, {})
            if (
                time.monotonic() - s.get("seen", 0) > 3
                or (s.get("session"), s.get("epoch"), self.generations.get(npc, 0))
                != stamp
                or s.get("mode") != "auto"
                or s.get("dead")
                or s.get("combat")
                or s.get("possessed")
                or (s.get("conversation_active") and not scene_exchange)
                or npc in self.busy
                or s.get("checkins_protocol") != 1
            ):
                return False
            if self.action_jobs.get(npc, {}).get("status") in (
                "pending",
                "running",
                "waiting for player",
            ):
                return False
        a, b = (self.states[n] for n in item["pair"])
        if scene_exchange:
            radius = min(
                self.action_config["npcs"][n]["nearby"].get("radius", 8)
                for n in item["pair"]
            )
            return (
                a.get("area") == b.get("area")
                and (a.get("x", 0) - b.get("x", 0)) ** 2
                + (a.get("y", 0) - b.get("y", 0)) ** 2
                <= radius * radius
            )
        # IDs in this list are emitted only for nearby, visible bound NPCs.
        return item["pair"][1] in a.get("nearby_npcs", []) and item["pair"][0] in b.get(
            "nearby_npcs", []
        )

    def checkin_reports(self, npc):
        """Only this NPC's received, game-confirmed reports; no other NPC's lore."""
        with self.store.lock:
            rows = self.store.db.execute(
                "SELECT text FROM messages WHERE npc=? AND player LIKE 'npc:%' "
                "AND speaker='player' ORDER BY id DESC LIMIT 6",
                (npc,),
            )
            return [row[0] for row in rows]

    def cancel_checkin(self, npc, reason="Interrupted"):
        item = self.checkin
        if item and npc in item["pair"]:
            self.checkin = None
            self.checkin_notice = reason

    def checkin_tick(self):
        if self.checkin and not self.checkin_valid(self.checkin):
            self.checkin_notice = "Check-in ended: player conversation, control change, distance or timeout."
            self.checkin = None
        self.scene_exchange_tick()

    def start_checkin(self, npc, stop, duty):
        target = duty.get("checkins", {}).get(stop)
        if not target or self.checkin or self.checkin_working or len(self.busy) >= 3:
            return
        key = npc + ":" + target
        now = time.time()
        if now - self.checkin_last.get(key, 0) < duty.get("checkin_cooldown", 300):
            return
        try:
            self.store.get(target)
        except ValueError:
            return
        item = dict(
            id=secrets.token_hex(12),
            pair=[npc, target],
            turn=0,
            social=bool(duty.get("social")),
            purpose=duty.get(
                "purpose", "A brief friendly check-in; do not invent trouble."
            ),
            deadline=time.monotonic() + 90,
            stamps={},
        )
        for n in item["pair"]:
            s = self.states.get(n, {})
            item["stamps"][n] = (
                s.get("session"),
                s.get("epoch"),
                self.generations.get(n, 0),
            )
            if self.action_jobs.get(n, {}).get("status") in (
                "pending",
                "running",
                "waiting for player",
            ):
                return
        if not self.checkin_valid(item):
            self.checkin_notice = "Check-in skipped: both NPCs must be visible, within 6 metres and idle in AUTO."
            return
        if not self.request_budget.admit("npc-checkins"):
            return
        self.checkin_last[key] = now
        self.set_setting("checkin_last", self.checkin_last)
        self.checkin = item
        self.checkin_notice = "Preparing NPC check-in"
        self.checkin_working += 1
        self.pool.submit(self.generate_checkin, item)

    def generate_checkin(self, item):
        try:
            with self.lock:
                if self.checkin is not item or not self.checkin_valid(item):
                    return
                speaker = item["pair"][item["turn"]]
                listener = item["pair"][1 - item["turn"]]
                partner = self.store.get(listener)
                profile = dict(
                    self.store.get(speaker), world_lore=self.store.world_lore()
                )
                profile["access_lore"] = self.store.lore_for(profile)
                profile["checkin"] = dict(
                    partner=partner["name"],
                    purpose=item.get("purpose", ""),
                )
                profile["perception"] = perception.snapshot(self.states[speaker])
                profile["surroundings"] = profile["perception"]["objects"]
                profile["checkin_reports"] = self.checkin_reports(speaker)
                if item.get("scene"):
                    profile["encounter"] = self.encounter_context(speaker)
                config = dict(self.config)
                policy = safeguards.settings(self.safeguard_policy)
                history = self.store.transcript(speaker, "npc:" + listener, 8)
                prompt = (
                    "Begin a brief friendly check-in with this colleague. Ask how things are; do not invent trouble."
                    if item["turn"] == 0
                    else "Answer the colleague's last spoken question briefly, using only your own knowledge. It is fine to have nothing to report."
                )
                if item.get("social"):
                    prompt = (
                        (
                            "Start a natural, brief conversation with this neighbour in one short sentence of at most 20 words. "
                            "Vary the topic from recent exchanges: share an interest, a personal opinion, something from your work, "
                            "or a detail from your own permitted lore or memories, or ask one related question instead. "
                            "You need not begin with a greeting or request a status report. "
                            if item["turn"] == 0
                            else "Respond naturally to your neighbour in one short sentence of at most 20 words. Add a relevant thought, opinion or "
                            "detail from your own knowledge rather than just acknowledging or reporting that all is well. "
                        )
                        + "Introduce information your neighbour may not know, but do not invent world events, completed actions, possessions or private lore you cannot share. Use only one thought or question, ideally 8–15 words, never more than 20 words."
                    )
                history.append(dict(speaker="player", text=prompt))
                if item.get("scene"):
                    history[-1]["text"] = (
                        "Speak one short in-character sentence for this scene, reacting to your partner's last words and your own current role. You may address the nearby rescuer. Do not greet captors as friends or invent actions. "
                        + item["purpose"]
                    )
                memories = self.store.memories(speaker, "npc:" + listener)
            profile = safeguards.scrub_tree(profile, policy)
            memories = safeguards.scrub_tree(memories, policy)
            history = safeguards.scrub_tree(history, policy)
            for row in history:
                if self.validation.check(row["text"], "input", profile):
                    raise ValueError("Check-in history blocked")
            if self.validation.error:
                raise ValueError("Validation unavailable")
            incoming = "\n".join(row["text"] for row in history)
            if (
                self.review_dialogue(speaker, incoming, "input", policy, {}, config)
                != "allow"
            ):
                raise ValueError("Check-in input withheld")
            with provider.observe_requests(
                self.usage.recorder(speaker, "npc_checkin", config)
            ):
                text = provider.reply(
                    config, profile, memories, guardrails.clean_history(history)
                )
            text = provider.game_speech(safeguards.scrub(text, policy)[0])
            if (
                not text.strip()
                or self.validation.check(text, "output", profile)
                or self.validation.error
            ):
                raise ValueError("Check-in output blocked")
            sources = (
                safeguards.trusted_sources(profile, memories)
                if policy["lore_check"]
                else {}
            )
            if (
                self.review_dialogue(speaker, text, "output", policy, sources, config)
                != "allow"
            ):
                raise ValueError("Check-in output withheld")
            with self.lock:
                if self.checkin is not item or not self.checkin_valid(item):
                    return
                peer = self.states[listener]
                authority = {}
                if item.get("scene"):
                    scene = self.director_scenes()[item["scene"]]
                    authority = dict(
                        encounter=item["scene"],
                        token=str(item["activation"]),
                        leader=next(iter(scene["actors"])),
                        **self.scene_authority(scene),
                    )
                item["request"] = self.command(
                    speaker,
                    "checkin_say",
                    text=text,
                    peer=listener,
                    peer_epoch=peer["epoch"],
                    checkin_id=item["id"],
                    world=self.config["world_id"],
                    **authority,
                )
                self.checkin_notice = "Waiting for game confirmation"
        except Exception as exc:
            with self.lock:
                if self.checkin is item:
                    self.checkin = None
                    self.checkin_notice = (
                        "Check-in withheld or failed: " + type(exc).__name__
                    )
        finally:
            with self.lock:
                self.checkin_working -= 1

    def checkin_ack(self, pending, event):
        item = self.checkin
        if (
            not item
            or item.get("request") != event.get("request")
            or pending.get("checkin_id") != item["id"]
        ):
            return
        speaker = pending["npc"]
        if (
            event.get("world") != self.config["world_id"]
            or event.get("session") != item["stamps"][speaker][0]
            or event.get("epoch") != item["stamps"][speaker][1]
        ):
            return
        if event.get("ok") != 1:
            self.cancel_checkin(
                speaker, "Check-in rejected by game; no conversation replayed."
            )
            return
        peer = pending["peer"]
        self.store.message(speaker, "npc:" + peer, "npc", pending["text"])
        name = self.store.get(speaker)["name"]
        self.store.message(
            peer,
            "npc:" + speaker,
            "player",
            name + " reported (unverified): " + pending["text"],
        )
        if item["turn"] == 1:
            self.cancel_checkin(
                speaker, "Check-in completed; conversation retained for both NPCs."
            )
        elif self.checkin_valid(item) and self.request_budget.admit("npc-checkins"):
            item["turn"] = 1
            self.checkin_working += 1
            self.pool.submit(self.generate_checkin, item)
        else:
            self.cancel_checkin(speaker, "Check-in interrupted before reply")
