"""Application composition, game event dispatch, and Redis command transport."""

from .authoring import creature_build, BUILD_DEFAULTS
import concurrent.futures
import hashlib
import json
import secrets
import threading
import time

from . import (
    provider,
    backup,
    guardrails,
    safeguards,
    conversation,
    actions,
    merchants,
    story,
    perception,
    nearby,
)
from .companions import CompanionService
from .action_service import ActionService
from .services.dialogue import DialogueService
from .services.npcs import NPCService
from .services.world import WorldService
from .encounters import EncounterService
from .live_encounters import LiveEncounterService
from .live_director import LiveDirectorService
from .persistent_director import PersistentDirectorService
from .social_service import SocialCheckService
from .translation_service import TranslationService
from . import __version__
from .recovery import RecoveryBackups
from .redis_wire import Redis
from .store import Store
from .usage import Usage
from .llm_settings import Settings
from .knowledge import inspect_knowledge


class Service(
    CompanionService,
    DialogueService,
    NPCService,
    WorldService,
    ActionService,
    EncounterService,
    LiveEncounterService,
    LiveDirectorService,
    PersistentDirectorService,
    SocialCheckService,
    TranslationService,
):
    """Own runtime state and dispatch game events to domain service methods.

    Domain mixins deliberately use this same instance: separate copies would
    break generation cancellation and game acknowledgement ordering.
    """

    def __init__(self, directory, config):
        self.directory, self.config = directory, config
        directory.mkdir(parents=True, exist_ok=True)
        self.llm = Settings(directory, config)
        self.config = config = self.llm.runtime()
        salt = directory / "identity_salt"
        if not salt.exists():
            salt.write_text(secrets.token_hex(32))
            salt.chmod(0o600)
        self.salt = salt.read_text().strip()
        self.store = Store(directory / "roleweaver.sqlite3")
        self.usage = Usage(directory / "usage.sqlite3", config)
        row = self.store.db.execute(
            "SELECT value FROM backup_settings WHERE key='identity_salt'"
        ).fetchone()
        if row:
            self.salt = row[0]
        row = self.store.db.execute(
            "SELECT value FROM backup_settings WHERE key='placement_restore_hold'"
        ).fetchone()
        self.placement_restore_hold = json.loads(row[0]) if row else {}
        self.name_privacy_cutoff = self.setting("name_privacy_cutoff", time.time())
        self.set_setting("name_privacy_cutoff", self.name_privacy_cutoff)
        self.control_sessions = self.setting("control_sessions", {})
        self.startup_auto = self.setting("startup_auto", True)
        self.suppressed_session = self.setting("suppressed_session", "")
        self.world_session = ""
        self.dms = {}
        self.restoring = False
        self.redis = Redis(port=config.get("redis_port", 6379))
        self.prefix = config.get("redis_prefix", "roleweaver:v1")
        self.lock = threading.RLock()
        self.states, self.busy, self.generations, self.pending = {}, set(), {}, {}
        self.last_reply = {}
        self.waiting_replies = {}
        self.request_budget = guardrails.RequestBudget(
            config.get("requests_per_player_per_minute", 6),
            config.get("requests_per_minute", 60),
        )
        self.guard_counts = dict(input_blocked=0, replies_replaced=0, rate_limited=0)
        self.validation = guardrails.ValidationEngine(
            config.get("guardrails_ai", False)
        )
        self.safeguard_policy = safeguards.settings(self.setting("safeguards", None))
        saved_conversation = self.setting("conversation", None)
        self.conversation_policy = conversation.migrate(saved_conversation)
        self.conversation_revision = (
            secrets.token_hex(12)
            if saved_conversation != self.conversation_policy
            else self.setting("conversation_revision", secrets.token_hex(12))
        )
        self.set_setting("conversation", self.conversation_policy)
        self.set_setting("conversation_revision", self.conversation_revision)
        self.conversation_hello = {}
        self.conversation_sent = 0
        self.init_companions()
        self.init_actions()
        self.init_encounters()
        self.init_live_encounters()
        self.init_director()
        self.init_social_checks()
        self.diagnostics = {}
        self.operations = {}
        self.restore_attempts = {}
        self.error = ""
        self.running = True
        self.stop_event = threading.Event()
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.redis_ok = False
        self.recovery = RecoveryBackups(
            directory / "recovery-backups", self.backup_data, config
        )

    def llm_status(self):
        with self.lock:
            return self.llm.status()

    def save_llm(self, body):
        with self.lock:
            if self.restoring:
                raise ValueError("Wait for restore to finish")
            self.companion_generation = secrets.token_hex(12)
            self.companion_states.clear()
            self.companion_pending.clear()
            self.config = self.llm.save(body)
            self.usage.configure(self.config)
            for npc in self.busy:
                self.generations[npc] = self.generations.get(npc, 0) + 1
            return self.llm.status()

    def probe_llm(self, body, models=False):
        # Capture settings under lock; network IO must not block game events.
        with self.lock:
            import copy

            settings = copy.copy(self.llm)
            settings.data = copy.deepcopy(self.llm.data)
        if models:
            return settings.probe(body, True)
        kind, p = settings.candidate(body)
        with provider.observe_requests(
            self.usage.recorder("", "connection_test", settings.runtime(kind, p))
        ):
            return settings.probe(body, False)

    def start(self):
        self.translation_start()
        if not hasattr(self, "database_recovery"):
            self.recovery.start()
        self.bridge_thread = threading.Thread(
            target=self.loop, daemon=True, name="game-bridge"
        )
        self.bridge_thread.start()

    def quiesce(self):
        """Drain every writer before recovery touches database files.

        Provider calls may still be in flight. Waiting for their workers prevents
        a late reply from writing into a database after it has been restored.
        HTTP callers must be drained by RecoveryRuntime first.
        """
        self.running = False
        if hasattr(self, "stop_event"):
            self.stop_event.set()
        if hasattr(self, "lock"):
            with self.lock:
                self.restoring = True
                for npc in self.busy:
                    self.generations[npc] = self.generations.get(npc, 0) + 1
        if hasattr(self, "recovery"):
            self.recovery.stop.set()
            if self.recovery.thread:
                self.recovery.thread.join()
        for name in ("bridge_thread", "translation_thread"):
            thread = getattr(self, name, None)
            if thread and thread is not threading.current_thread():
                thread.join()
        if hasattr(self, "pool"):
            self.pool.shutdown(wait=True, cancel_futures=True)

    def close(self):
        self.quiesce()
        for obj in (getattr(self, "store", None), getattr(self, "_translations", None)):
            if obj:
                with obj.lock:
                    obj.db.close()

    def loop(self):
        from .diagnostics_log import record

        while self.running:
            try:
                raw = self.redis.call("LPOP", self.prefix + ":events")
                self.redis_ok = True
                if raw:
                    self.event(json.loads(raw))
                else:
                    time.sleep(0.05)
                self.thinking_tick()
                self.director_tick()
                with self.lock:
                    for k, v in list(self.pending.items()):
                        if time.monotonic() - v["time"] >= 30:
                            record(self, "game_confirmation_timeout")
                            if v["kind"] == "encounter_end":
                                self.director_command_result(v, False)
                            if v["kind"] in ("move_dm", "despawn", "persistence"):
                                self.operations[v["npc"]] = dict(
                                    status="failed",
                                    message="Game confirmation timed out; check connection before retrying.",
                                )
                            if v["kind"] == "action_capture":
                                self.action_notice = "Location capture timed out; retry after checking the game connection."
                            self.pending.pop(k, None)
            except Exception as exc:
                record(self, "bridge_failed", exc)
                self.redis_ok = False
                self.error = "Bridge error: " + type(exc).__name__
                time.sleep(1)

    def snapshot(self):
        with self.lock:
            states = {
                k: dict(
                    v,
                    perception=perception.snapshot(v),
                    connected=time.monotonic() - v["seen"] < 4,
                    thinking=k in self.busy,
                    pending_control=any(
                        p["npc"] == k and p["kind"] == "mode"
                        for p in self.pending.values()
                    ),
                )
                for k, v in self.states.items()
            }
            return {
                "version": __version__,
                "provider": self.config["provider"],
                "llm_service": self.llm.data["active"],
                "model": self.config.get("model", ""),
                "redis": self.redis_ok,
                "placement_owner": self.config.get("placement_owner", "world"),
                "draft_scope": hashlib.sha256(
                    (
                        str(self.directory.resolve()) + self.config.get("world_id", "")
                    ).encode()
                ).hexdigest()[:24],
                "world_name": self.config.get(
                    "world_name", self.config.get("world_id", "")
                ),
                "error": self.error,
                "npcs": self.store.list_npcs(),
                "states": states,
                "placements": self.store.placements(),
                "diagnostics": {
                    p["id"]: self.npc_diagnostic(p["id"])
                    for p in self.store.list_npcs()
                },
                "operations": dict(self.operations),
                "guardrails": dict(
                    self.guard_counts,
                    per_player=self.request_budget.per_player,
                    per_minute=self.request_budget.global_limit,
                    sdk=self.validation.status(),
                ),
                "startup_auto": self.startup_auto,
                "spawn_enabled": bool(self.config.get("allow_dm_spawn", False)),
                "dms": [
                    dict(v, id=k)
                    for k, v in self.dms.items()
                    if time.monotonic() - v["seen"] < 3
                ],
            }

    def event(self, event):
        if not isinstance(event, dict):
            self.error = "Ignored a malformed game event. Check the NWN script log."
            return
        kind = event.get("kind")
        npc = event.get("npc", "")
        if kind == "hello":
            with self.lock:
                self.companion_hello(event)
        if kind in ("companion_state", "companion_chat", "companion_ack"):
            self.companion_event(event)
            return
        if kind in ("companion_preferences_get", "companion_preferences_set"):
            self.companion_preferences_event(event)
            return
        if kind in (
            "translation_player",
            "translation_preference",
            "translation_examine",
            "translation_dialogue",
            "translation_names",
        ):
            self.translation_event(event)
            return
        if kind == "payment_result":
            with self.lock:
                self.payment_event(event)
            return
        if kind == "merchant_stock":
            with self.lock:
                self.merchant_event(event)
            return
        if kind == "action_capture":
            self.action_capture_event(event)
            return
        if kind == "dm_available":
            with self.lock:
                self.dms[event["dm"]] = {
                    k: event[k] for k in ("name", "token", "session", "tick")
                }
                self.dms[event["dm"]].update(
                    {
                        k: event[k]
                        for k in (
                            "live_protocol",
                            "area_object",
                            "area",
                            "area_tag",
                            "area_name",
                            "x",
                            "y",
                            "z",
                            "facing",
                        )
                        if k in event
                    }
                )
                self.dms[event["dm"]]["seen"] = time.monotonic()
            return
        if kind == "social_result":
            with self.lock:
                self.social_result(event)
            return
        if kind == "director_observation":
            with self.lock:
                self.director_observe(event)
            return
        if kind == "encounter_event":
            with self.lock:
                if not self.live_game_event(event):
                    self.encounter_game_event(event)
            return
        if kind == "hello":
            with self.lock:
                self.tick_live(event)
                self.encounter_session(event)
                self.sync_encounter_reactions(event)
            self.sync_conversation(event)
            self.world_session = event.get("session", "")
            self.restore(event)
            return
        if kind == "placement":
            if self.live_for(npc):
                return
            if self.placement_restore_hold.get(event.get("world")) == event.get(
                "session"
            ):
                return
            if self.config.get("placement_owner", "world") != "roleweaver" and not (
                self.config.get("allow_persistent_spawn")
                and event.get("source") == "dm_persistent"
            ):
                return
            try:
                self.store.save_placement(event)
            except ValueError:
                self.error = "Placement could not be saved. Create the NPC profile before binding it."
            return
        if kind == "state":
            try:
                profile = self.store.get(npc)
            except ValueError:
                profile = None
            with self.lock:
                previous = self.states.get(npc, {})
                if (previous.get("session"), previous.get("epoch")) != (
                    event["session"],
                    event["epoch"],
                ):
                    self.generations[npc] = self.generations.get(npc, 0) + 1
                self.states[npc] = {
                    k: event[k] for k in ("session", "epoch", "tick", "mode", "object")
                }
                self.states[npc].update(
                    {
                        k: event[k]
                        for k in (
                            "source",
                            "area",
                            "area_resref",
                            "area_tag",
                            "x",
                            "y",
                            "dead",
                            "possessed",
                            "nearby_players",
                            "appearance",
                            "level",
                            "npc_class",
                        )
                        if k in event
                    }
                )
                self.states[npc]["seen"] = time.monotonic()
                self.states[npc]["combat_phase"] = event.get("combat_phase", "")
                self.reconcile_encounter_combat(npc, event)
                self.states[npc]["combat"] = event.get("combat", 0)
                self.states[npc]["live_owner"] = event.get("live_owner", "")
                self.states[npc]["encounter_protocol"] = event.get(
                    "encounter_protocol", 0
                )
                self.action_state(npc, event)
                self.sync_merchant(npc, event)
                self.states[npc]["surroundings"] = perception.observations(
                    event.get("surroundings", []),
                    area_wide=event.get("perception_protocol") == 3,
                )
                self.states[npc]["nearby_targets"] = nearby.targets(
                    event.get("surroundings", []),
                    area_wide=event.get("perception_protocol") == 3,
                )
                for field in (
                    "nearby_protocol",
                    "follow_protocol",
                    "perception_protocol",
                    "perception_truncated",
                    "inventory_protocol",
                    "inventory_revision",
                    "inventory",
                    "perception_tick",
                    "self_condition",
                    "nearby_npcs",
                    "conversation_active",
                    "checkins_protocol",
                    "scene_speech_protocol",
                    "scene_speech_status",
                    "retreat_protocol",
                ):
                    self.states[npc][field] = event.get(field)
                self.sync_inventory(npc, event)
                for field in (
                    "interaction_protocol",
                    "interaction_revision",
                    "npc_combat_target",
                ):
                    self.states[npc][field] = event.get(field)
                self.sync_interactions(npc, event)
                self.visit_tick(npc)
                self.checkin_tick()
                self.patrol_tick(npc, event)
                self.village_tick(npc, event)
                last_session = self.control_sessions.get(npc)
                restoring = next(
                    (
                        p
                        for p in self.pending.values()
                        if p["npc"] == npc
                        and p["kind"] == "restore"
                        and p.get("session") == event["session"]
                        and not p.get("startup_handled")
                    ),
                    None,
                )
                startup = bool(restoring) or (
                    last_session is not None
                    and last_session != event["session"]
                    and event["tick"] <= 5
                )
                if restoring is not None:
                    restoring["startup_handled"] = True
                if profile and last_session != event["session"]:
                    self.control_sessions[npc] = event["session"]
                    self.set_setting("control_sessions", self.control_sessions)
                if (
                    profile
                    and startup
                    and not event.get("live_owner")
                    and self.startup_auto
                    and not self.restoring
                    and event["session"] != self.suppressed_session
                    and profile["mode"] != "dm"
                    and event["mode"] == "paused"
                    and not event.get("possessed")
                    and not event.get("dead")
                ):
                    self.control(npc, "auto")
                if profile and profile["mode"] != event["mode"]:
                    profile["mode"] = event["mode"]
                    self.store.save(profile)
            return
        if kind == "scene_line":
            with self.lock:
                run = self.encounters["runs"].get(event.get("encounter"), {})
                state = self.states.get(npc, {})
                if (
                    run.get("status") != "active"
                    or event.get("session") != run.get("session")
                    or event.get("epoch") != state.get("epoch")
                    or event.get("token") != str(run.get("started"))
                    or event.get("world") != self.config["world_id"]
                ):
                    return
                actor = next(
                    (a for a in run["template"]["actors"] if a["npc"] == npc), {}
                )
                if actor.get("opening") and event.get("text") == actor["opening"]:
                    self.store.message(
                        npc, "npc:scene:" + event["encounter"], "npc", event["text"]
                    )
            return
        if kind == "payment_request":
            with self.lock:
                state = self.states.get(npc, {})
                if (
                    event.get("world") != self.config["world_id"]
                    or event.get("session") != state.get("session")
                    or event.get("epoch") != state.get("epoch")
                    or not event.get("listener")
                ):
                    return
                choices = self.payment_choices(npc, event["listener"])
                amount = (
                    self.action_config["npcs"]
                    .get(npc, {})
                    .get("payment", {})
                    .get("amount")
                )
                choice = "payment:" + str(amount)
                if choice in {c["id"] for c in choices}:
                    self.run_interaction(npc, choice, event["listener"])
            return
        if kind == "ack":
            with self.lock:
                pending = self.pending.pop(event.get("request"), None)
                if pending and pending["kind"] in ("live_spawn", "live_cleanup"):
                    self.live_ack(pending, event)
                elif pending and pending["kind"] == "checkin_say":
                    self.checkin_ack(pending, event)
                elif pending and pending["kind"] == "merchant_stock_edit":
                    self.merchant_ack(pending, event)
                elif pending and pending["kind"] in (
                    "controlled_action",
                    "controlled_stop",
                    "merchant_setup",
                    "payment_offer",
                    "npc_attack",
                ):
                    self.action_ack(pending, event)
                elif pending and pending["kind"] in (
                    "move_dm",
                    "despawn",
                    "persistence",
                ):
                    target = pending["npc"]
                    if event.get("ok") == 1:
                        if (
                            pending["kind"] == "persistence"
                            and pending.get("persistence") == "temporary"
                        ) or (
                            pending["kind"] == "despawn"
                            and pending.get("return_mode") == "never"
                        ):
                            with self.store.lock, self.store.db:
                                self.store.db.execute(
                                    "DELETE FROM placements WHERE npc=? AND world=?",
                                    (target, self.config.get("world_id", "")),
                                )
                        if pending["kind"] == "despawn":
                            self.states.pop(target, None)
                        self.operations[target] = dict(
                            status="confirmed",
                            message={
                                "move_dm": "Moved to DM; AI paused.",
                                "persistence": "Persistence updated; AI paused.",
                                "despawn": "Creature despawned; profile and memories retained.",
                            }[pending["kind"]],
                        )
                    else:
                        self.operations[target] = dict(
                            status="failed",
                            message="Game rejected the action. Check possession, ownership, DM connection and NPC state.",
                        )
                elif (
                    pending
                    and pending["kind"] == "spawn_dm"
                    and event.get("ok") == 1
                    and pending.get("persistence") == "temporary"
                ):
                    with self.store.lock, self.store.db:
                        self.store.db.execute(
                            "DELETE FROM placements WHERE npc=? AND world=?",
                            (pending["npc"], self.config.get("world_id", "")),
                        )
                elif pending and pending["kind"] == "delete" and event.get("ok") == 1:
                    self.finish_delete(pending["npc"])
                elif pending and pending["kind"] == "social_roll":
                    if event.get("ok") != 1:
                        self.social_rejected(pending)
                elif pending and pending["kind"] == "encounter_end":
                    self.director_command_result(pending, event.get("ok") == 1)
                elif pending and pending["kind"] == "say" and event.get("ok") == 1:
                    if not pending.get("transient"):
                        self.store.message(
                            pending["npc"], pending["player"], "npc", pending["text"]
                        )
                    if pending.get("action_choice"):
                        try:
                            self.run_action(
                                pending["npc"],
                                pending["action_choice"],
                                pending.get("listener", ""),
                                pending.get("action_generation"),
                            )
                        except ValueError:
                            self.action_notice = (
                                "A proposed action became unavailable before execution."
                            )
                elif pending and event.get("ok") != 1:
                    self.error = (
                        "Spawn rejected: check DM availability, profile binding and the world spawn settings."
                        if pending["kind"] == "spawn_dm"
                        else (
                            "NPC restoration failed: "
                            + event.get("reason", "check area and blueprint")
                            if pending["kind"] == "restore"
                            else "Game rejected a stale or unavailable NPC command; nothing was spoken."
                        )
                    )
            return
        if (
            kind != "chat"
            or not isinstance(event.get("text"), str)
            or len(event["text"]) > 2000
        ):
            return
        with self.lock:
            if self.restoring:
                return
            if (
                "conversation_revision" in event
                and event["conversation_revision"] != self.conversation_revision
            ):
                return
            try:
                self.store.get(npc)
            except ValueError:
                return
            state = self.states.get(npc)
            if not state or time.monotonic() - state["seen"] > 4:
                return
            if (
                event.get("session") != state["session"]
                or event.get("epoch") != state["epoch"]
            ):
                return
            if not self.store.once(str(event["event_id"])):
                return
            self.cancel_checkin(npc, "Player conversation takes priority")
            player = hashlib.sha256((self.salt + event["player"]).encode()).hexdigest()[
                :24
            ]
            self.diagnostics[npc] = dict(last_chat=time.time(), error="")
            display_name = event["player"].partition(":")[2]
            speech = event["text"]
            # Support the old bridge until its compiled scripts are reloaded.
            if (
                event.get("speech_format") != 1
                and display_name
                and speech.startswith(display_name + ": ")
            ):
                speech = speech[len(display_name) + 2 :]
            speech, masked = safeguards.scrub(speech, self.safeguard_policy)
            if masked:
                self.safeguard_event(npc, "input", masked, "masked")
            speech_id = self.store.message(npc, player, "player", speech)
            profile = dict(self.store.get(npc), world_lore=self.store.world_lore())
            profile["access_lore"] = self.store.lore_for(profile)
            profile["_combat_turn"] = dict(
                event_id=event.get("event_id", ""),
                attack_ready=event.get("combat_attack_ready") == 1,
            )
            self.director_chat(npc, player, event)
            profile["story"] = story.context(event.get("story"))
            if profile["story"].get("visit"):
                profile["story_first_message"] = self.store.story_visit_start(
                    npc, player, profile["story"]["visit"], speech_id
                )
            if (
                state["mode"] != "auto"
                or state.get("combat")
                or state.get("dead")
                or npc in self.busy
                or time.monotonic() - self.last_reply.get(npc, 0) < 2
            ):
                return
            if len(self.busy) >= 4 or not self.request_budget.admit(player):
                self.guard_counts["rate_limited"] += 1
                self.diagnostics[npc][
                    "error"
                ] = "Reply deferred: request limit reached. Try again shortly."
                return
            self.busy.add(npc)
            generation = self.generations.get(npc, 0)
            self.pool.submit(
                self.generate,
                npc,
                player,
                profile,
                generation,
                dict(state),
                event.get("listener", ""),
                display_name,
                bool(guardrails.input_reason(speech)),
                speech,
                speech_id,
                event.get("merchant_quote"),
            )

    def command(self, npc, kind, **fields):
        with self.lock:
            state = self.states.get(npc)
            if not state or time.monotonic() - state["seen"] > 3:
                raise ValueError("NPC is not connected to the game")
            request = secrets.token_hex(12)
            if kind == "say":
                fields["conversation_revision"] = self.conversation_revision
            command = {
                "kind": kind,
                "npc": npc,
                "session": state["session"],
                "epoch": state["epoch"],
                "expires": state["tick"] + 5,
                "request": request,
                **fields,
            }
            self.pending[request] = {
                "npc": npc,
                "kind": kind,
                "time": time.monotonic(),
                **fields,
            }
            try:
                self.redis.call(
                    (
                        "LPUSH"
                        if kind
                        in (
                            "mode",
                            "delete",
                            "move_dm",
                            "despawn",
                            "persistence",
                            "controlled_stop",
                        )
                        else "RPUSH"
                    ),
                    self.prefix + ":commands",
                    json.dumps(command),
                )
                self.redis.call("LTRIM", self.prefix + ":commands", 0, 63)
                self.redis.call("EXPIRE", self.prefix + ":commands", 10)
            except Exception:
                self.pending.pop(request, None)
                raise
            return request

    def restore(self, hello):
        # The game sends this even when it contains no bound NPCs. Commands are
        # session-scoped, and only placements from an earlier module run return.
        if (
            (
                self.config.get("placement_owner", "world") != "roleweaver"
                and not self.config.get("allow_persistent_spawn")
            )
            or not hello.get("owns_placements")
            or int(hello.get("tick", 0)) < 4
        ):
            return
        with self.lock:
            session = hello["session"]
            for placement in self.store.placements(hello["world"]):
                if (
                    self.config.get("placement_owner", "world") != "roleweaver"
                    and placement["source"] != "dm_persistent"
                ):
                    continue
                if (
                    self.config.get("placement_owner", "world") != "roleweaver"
                    and placement["source"] != "dm_persistent"
                ):
                    continue
                npc = placement["npc"]
                if placement["session"] == session or placement["dead"]:
                    continue
                key = (session, npc)
                attempts, last = self.restore_attempts.get(key, (0, 0))
                if attempts >= 3 or time.monotonic() - last < 10:
                    continue
                request = secrets.token_hex(12)
                command = dict(
                    placement,
                    kind="restore",
                    session=session,
                    epoch=0,
                    expires=hello["tick"] + 5,
                    request=request,
                )
                self.pending[request] = {
                    "npc": npc,
                    "kind": "restore",
                    "session": session,
                    "time": time.monotonic(),
                }
                self.redis.call("RPUSH", self.prefix + ":commands", json.dumps(command))
                self.redis.call("EXPIRE", self.prefix + ":commands", 10)
                self.restore_attempts[key] = (attempts + 1, time.monotonic())

    def setting(self, key, default):
        row = self.store.db.execute(
            "SELECT value FROM backup_settings WHERE key=?", (key,)
        ).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key, value):
        with self.store.lock, self.store.db:
            self.store.db.execute(
                "INSERT OR REPLACE INTO backup_settings VALUES (?,?)",
                (key, json.dumps(value)),
            )
