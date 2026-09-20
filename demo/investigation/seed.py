"""Seed demo-owned profiles and documents without deleting player memories.

Run with the companion stopped, after backing up its entire data directory.
Existing innkeeper/merchant names, appearance, inventory and memories are retained.
"""

import argparse, json, sys
from pathlib import Path


def seed(database, content, world):
    from roleweaver.store import Store, DEFAULT_NPC
    from roleweaver import actions

    value = json.loads(content.read_text())
    s = Store(database)
    try:
        for p in value["profiles"]:
            s.save(
                dict(DEFAULT_NPC, **{k: v for k, v in p.items() if k in DEFAULT_NPC})
            )
        for id, doc in [
            ("tavern_owner", "rq_innkeeper"),
            ("merchant_one", "rq_merchant"),
        ]:
            p = s.get(id)
            lore = next(d["text"] for d in value["access_lore"] if d["id"] == doc)
            p["lore"] = lore
            s.save(p)
        for update in value.get("profile_updates", []):
            p = s.get(update["id"])
            p.update({k: update[k] for k in ("personality", "voice")})
            s.save(p)
        for d in value["world_documents"]:
            s.save_world_document(d)
        for d in value["access_lore"]:
            s.save_access_lore(d)
        row = s.db.execute(
            "SELECT value FROM backup_settings WHERE key='controlled_actions'"
        ).fetchone()
        c = actions.settings(json.loads(row[0]) if row else None)
        for id, name, x, y in [
            ("welcome_table", "Visitor table", 20, 30),
            ("merchant_stall", "Merchant stall", 20, 38),
            ("arcane_corner", "Wizard study", 30, 39),
            ("chapel_shrine", "Chapel shrine", 30, 47),
            ("royal_dais", "Royal dais", 25, 48),
            ("guard_post", "Entrance guard post", 22, 21),
            ("holt_desk", "Quartermaster station", 22, 45),
        ]:
            c["destinations"][id] = dict(
                id=id,
                name=name,
                world=world,
                area="throne_room",
                area_tag="throne_room",
                x=x,
                y=y,
                z=0,
                facing=90,
            )
        for id, home in [
            ("tavern_owner", "welcome_table"),
            ("merchant_one", "merchant_stall"),
            ("rq_guard", "guard_post"),
            ("rq_wizard", "arcane_corner"),
            ("rq_cleric", "chapel_shrine"),
            ("rq_holt", "holt_desk"),
        ]:
            old = c["npcs"].get(id, actions.DEFAULT_POLICY)
            c["npcs"][id] = dict(
                old,
                enabled=True,
                destinations=list(
                    dict.fromkeys(
                        old["destinations"]
                        + [
                            "welcome_table",
                            "merchant_stall",
                            "arcane_corner",
                            "chapel_shrine",
                            "royal_dais",
                            "guard_post",
                            "holt_desk",
                        ]
                    )
                ),
                lead_destinations=list(
                    dict.fromkeys(
                        old["lead_destinations"]
                        + [
                            "welcome_table",
                            "merchant_stall",
                            "arcane_corner",
                            "chapel_shrine",
                            "royal_dais",
                            "guard_post",
                            "holt_desk",
                        ]
                    )
                ),
                home=home,
                gestures=["greet", "bow", "salute"],
            )
        with s.db:
            s.db.execute(
                "INSERT OR REPLACE INTO backup_settings VALUES (?,?)",
                ("controlled_actions", json.dumps(actions.settings(c))),
            )
        print(
            "Seeded demo profiles, lore and destinations. Existing memories retained."
        )
    finally:
        s.db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--world", default="my_world")
    a = p.parse_args()
    sys.path.insert(0, str(a.source))
    seed(a.database, Path(__file__).with_name("content.json"), a.world)
