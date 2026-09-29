"""Player preferences and asynchronous translation, isolated from NPC reasoning."""

import hashlib
import json
import threading
import time
from .translation import CHARACTER_DESCRIPTION_BYTES, TranslationCache, translate
from . import provider
from .translation_surfaces import lookup_batch, name_context


class TranslationService:
    def translation_diagnostics(self):
        """Technical status only: no text, player identifiers or provider secrets."""
        with self.lock:
            cache = self.translations
            with cache.lock:
                counts = dict(
                    cache.db.execute(
                        "SELECT status,COUNT(*) FROM entries GROUP BY status"
                    )
                )
                settings = cache.config()
                worker = getattr(self, "translation_thread", None)
                return dict(
                    enabled=settings["enabled"],
                    source=settings["source"],
                    languages=settings["languages"],
                    per_minute=settings["per_minute"],
                    provider=self.config.get("provider", "offline"),
                    model=settings["model"] or self.config.get("model", ""),
                    worker_running=bool(worker and worker.is_alive()),
                    bridge_online=time.monotonic()
                    - self.conversation_hello.get("seen", -1e9)
                    < 4,
                    pending=len(cache.jobs),
                    cache_hits=cache.hits,
                    counts=counts,
                    worker_error=cache.worker_error,
                    native_adapter="Not probed by the companion; verify NWNX_RWTranslation in the NWNX startup log.",
                )

    @property
    def translations(self):
        with self.lock:
            if not hasattr(self, "_translations"):
                self._translations = TranslationCache(
                    self.directory / "translations.sqlite3"
                )
            return self._translations

    def translation_start(self):
        def worker():
            backup_at = 0
            while self.running:
                try:
                    cache = self.translations
                    cache.process_one(self.translation_request)
                    self.translation_deliver_ready()
                    if (
                        not hasattr(self, "database_recovery")
                        and time.monotonic() >= backup_at
                    ):
                        folder = self.directory / "translation-backups"
                        folder.mkdir(exist_ok=True)
                        cache.snapshot(folder / (str(time.time_ns()) + ".sqlite3"))
                        for old in sorted(folder.glob("*.sqlite3"))[:-5]:
                            old.unlink()
                        backup_at = time.monotonic() + 900
                    cache.worker_error = ""
                except Exception as exc:
                    # Do not expose provider details or stop NPC dialogue on failure.
                    if hasattr(self, "_translations"):
                        self._translations.worker_error = type(exc).__name__
                    self.stop_event.wait(5)
                self.stop_event.wait(0.5)

        self.translation_thread = threading.Thread(
            target=worker, daemon=True, name="world-translation"
        )
        self.translation_thread.start()

    def translation_request(self, row):
        with self.lock:
            config = dict(self.config)
        selected = self.translations.config()["model"]
        if selected:
            config["model"] = selected
        config["request_timeout"] = min(config.get("request_timeout", 25), 30)
        with provider.observe_requests(self.usage.recorder("", "translation", config)):
            return translate(
                config,
                row["source"],
                row["target"],
                row["kind"],
                row["original"],
                row["context"],
            )

    def translation_deliver_ready(self):
        """Complete bounded subscriptions for lines the game has already shown.

        This is a read-only cache check, never a crawler or a new translation job.
        No tokens in an open dialogue are rewritten; native code keeps the result
        for the player's next visit. Pending state is transient, not a world index.
        """
        with self.lock:
            pending = list(getattr(self, "_translation_waiting", {}).items())
        cache = self.translations
        cfg = cache.config()
        for key, (deadline, person, reply) in pending:
            pref = cache.preference(person)
            stale = (
                time.monotonic() > deadline
                or reply["session"] != self.world_session
                or not cfg["enabled"]
                or not pref["enabled"]
                or pref["language"] != reply["language"]
                or pref["language"] not in cfg["languages"]
            )
            row = reply["texts"][0]
            value = (
                None
                if stale
                else cache.ready(
                    "dialogue:"
                    + reply["dialogue"]
                    + ":"
                    + row["kind"]
                    + ":"
                    + str(row["id"]),
                    reply["language"],
                    row["kind"],
                    row["text"],
                    "dialogue:" + reply["dialogue"],
                )
            )
            if not stale and value is None:
                continue
            with self.lock:
                # A second visit can replace this subscription while the worker reads.
                if getattr(self, "_translation_waiting", {}).get(key) != (
                    deadline,
                    person,
                    reply,
                ):
                    continue
                self._translation_waiting.pop(key, None)
            if value:
                result = dict(reply, texts=[dict(row, translated=value)])
                self.redis.call("RPUSH", self.prefix + ":commands", json.dumps(result))
                self.redis.call("EXPIRE", self.prefix + ":commands", 10)

    def translation_event(self, event):
        if (
            event.get("world") != self.config["world_id"]
            or event.get("session") != self.world_session
        ):
            return
        identity = event.get("identity")
        if not isinstance(identity, str) or not 1 <= len(identity) <= 128:
            return
        if (
            not isinstance(event.get("player"), str)
            or not isinstance(event.get("token"), str)
            or not 1 <= len(event["token"]) <= 100
            or not 1 <= len(event["player"]) <= 32
        ):
            return
        if event.get("kind") not in {
            "translation_player",
            "translation_preference",
            "translation_examine",
            "translation_dialogue",
            "translation_names",
        }:
            return
        if type(event.get("tick")) is not int or type(event.get("seq")) is not int:
            return
        cache = self.translations
        person = hashlib.sha256(
            (self.salt + ":translation:" + identity).encode()
        ).hexdigest()
        kind = event["kind"]
        if kind == "translation_preference":
            cache.preference(
                person,
                dict(enabled=event.get("enabled") == 1, language=event.get("language")),
            )
        pref = cache.preference(person)
        cfg = cache.config()
        active = (
            cfg["enabled"] and pref["enabled"] and pref["language"] in cfg["languages"]
        )
        result = dict(
            kind="translation_reply",
            world=self.config["world_id"],
            session=event["session"],
            player=event["player"],
            token=event["token"],
            seq=event.get("seq"),
            expires=event["tick"] + 5,
            enabled=int(active),
            preference_enabled=int(pref["enabled"]),
            language=pref["language"],
            languages=cfg["languages"],
            service_enabled=int(cfg["enabled"]),
        )
        if kind in ("translation_dialogue", "translation_names"):
            result["texts"] = lookup_batch(cache, event, pref, active)
            result["kind"] = kind + "_reply"
            if kind == "translation_dialogue":
                result["dialogue"] = event["dialogue"]
                result["speaker"] = event.get("speaker")
                if event.get("on_demand") == 1:
                    result["on_demand"] = 1
                    result["expires"] = event["tick"] + 180
                    row = result["texts"][0]
                    key = (event["session"], event["player"], row["display_token"])
                    with self.lock:
                        if not hasattr(self, "_translation_waiting"):
                            self._translation_waiting = {}
                        self._translation_waiting.pop(key, None)
                        if (
                            active
                            and not row["translated"]
                            and pref["language"] != cfg["source"]
                        ):
                            if len(self._translation_waiting) >= 256:
                                self._translation_waiting.pop(
                                    next(iter(self._translation_waiting))
                                )
                            self._translation_waiting[key] = (
                                time.monotonic() + 180,
                                person,
                                result,
                            )
            self.redis.call("RPUSH", self.prefix + ":commands", json.dumps(result))
            self.redis.call("EXPIRE", self.prefix + ":commands", 10)
            return
        if kind == "translation_examine":
            # Both normal and AI NPCs expose their public Examine text. This
            # path never loads their AI profile, private lore, memories or chat.
            character_description = event.get("object_type") == 1 and event.get(
                "player_character"
            ) in (0, 1)
            player_description = (
                event.get("object_type") == 1 and event.get("player_character") == 1
            )
            if event.get("approved") != 1 or not (
                character_description
                or (
                    event.get("object_type") in (8, 16, 64)
                    and event.get("player_character", 0) == 0
                )
            ):
                return
            name, description = event.get("name"), event.get("description")
            if (
                not isinstance(name, str)
                or len(name) > 2000
                or not isinstance(description, str)
                or (
                    len(description.encode("utf-8")) > CHARACTER_DESCRIPTION_BYTES
                    if character_description
                    else len(description) > 2000
                )
            ):
                return
            mode = "preserve" if player_description else event.get("name_mode", "auto")
            if mode not in ("auto", "preserve", "translate"):
                return
            result.update(
                object=event.get("object"),
                source_name=name,
                source_description=description,
                request=event.get("request"),
                name="",
                description="",
                name_mode=mode,
            )
            if active:
                resource = str(event.get("object", ""))[:32]
                # Even an explicit label-translation policy cannot translate a
                # player's name. Do not send their name or character file resref
                # as provider context; cache only the public description itself.
                context = (
                    "public-player-description"
                    if player_description
                    else name_context(
                        event.get("resref", ""), event["object_type"], "auto"
                    )
                )
                for field, text in [("name", name), ("description", description)]:
                    if field == "name" and mode == "preserve":
                        continue
                    result[field] = (
                        cache.lookup(
                            event["session"] + ":" + resource + ":" + field,
                            pref["language"],
                            (
                                (
                                    "player_description"
                                    if player_description
                                    else "npc_description"
                                )
                                if field == "description" and character_description
                                else field
                            ),
                            text,
                            context
                            + (
                                ":label"
                                if field == "name" and mode == "translate"
                                else ""
                            ),
                        )
                        or ""
                    )
            result["display"] = (
                (result["name"] or name)
                + "\n\n"
                + (result["description"] or description)
            )
        elif kind not in ("translation_player", "translation_preference"):
            return
        self.redis.call("RPUSH", self.prefix + ":commands", json.dumps(result))
        self.redis.call("EXPIRE", self.prefix + ":commands", 10)
