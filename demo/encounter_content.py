"""Seed editable demo scenes without discarding existing runs or player memories."""

import copy
import json
import secrets
import time

from roleweaver import encounters
from roleweaver.live_director import initial


def armed_run(definition, world):
    """Use the same waiting state as the dashboard's Arm command."""
    now = time.time()
    return dict(
        template=copy.deepcopy(definition),
        status="waiting",
        stage=definition["stages"][0]["id"],
        outcome="",
        world=world,
        session="awaiting-game",
        revision=secrets.token_hex(12),
        started=now,
        updated=now,
        owner=secrets.token_hex(16),
        events=["Demo encounter armed; waiting for its actors and game bridge."],
        director=dict(initial(), enabled=definition["automation"]["enabled"]),
        check_results={},
        activation_events=[],
        recovery_reason="",
    )


def seed_encounters(store, definitions, world):
    row = store.db.execute(
        "SELECT value FROM backup_settings WHERE key='encounters'"
    ).fetchone()
    data = encounters.settings(json.loads(row[0]) if row else None)
    for raw in definitions:
        definition = encounters.definition(raw)
        key = definition["id"]
        data["templates"][key] = definition
        if key not in data["runs"] and definition["automation"]["enabled"]:
            data["runs"][key] = armed_run(definition, world)
    data = encounters.settings(data)
    with store.db:
        store.db.execute(
            "INSERT OR REPLACE INTO backup_settings VALUES ('encounters',?)",
            (json.dumps(data),),
        )
