"""DM inspection uses the same lore audience and context limits as generation."""

from .authoring import visible_lore


def inspect_knowledge(store, npc, player=""):
    if not isinstance(player, str) or len(player) > 128:
        raise ValueError("Invalid player reference")
    with store.lock:
        profile = store.get(npc)
        people = [
            dict(r)
            for r in store.db.execute(
                """SELECT player,MAX(created) AS last_seen FROM (
          SELECT player,created FROM messages WHERE npc=? UNION ALL SELECT player,created FROM memories WHERE npc=?
          ) WHERE player!='' GROUP BY player ORDER BY last_seen DESC""",
                (npc, npc),
            )
        ]
        if player and player not in {r["player"] for r in people}:
            raise ValueError("Unknown player history for this NPC")
        documents = store.world_documents()
        lore = []
        for entry in store.access_lore():
            included = bool(visible_lore([entry], profile))
            reason = (
                "Available to this NPC"
                if included
                else (
                    "Inactive"
                    if not entry["active"]
                    else (
                        "DM only"
                        if entry["audience"] == "dm"
                        else "Different NPC or faction"
                    )
                )
            )
            # Excluded entries are shown by title and reason only, never as this NPC's knowledge.
            lore.append(
                dict(
                    id=entry["id"],
                    title=entry["title"],
                    available=included,
                    reason=reason,
                    text=entry["text"] if included else "",
                    disclosure=entry["disclosure"] if included else "",
                )
            )
        memories = store.memories(npc, player)
        total = store.db.execute(
            "SELECT COUNT(*) FROM memories WHERE npc=? AND player IN ('',?)",
            (npc, player),
        ).fetchone()[0]
        history = store.transcript(npc, player, 16) if player else []
        return dict(
            npc=npc,
            name=profile["name"],
            player=player,
            players=people,
            profile={
                k: profile[k]
                for k in (
                    "role",
                    "personality",
                    "voice",
                    "lore",
                    "boundaries",
                    "guidance",
                    "factions",
                )
            },
            documents=[
                dict(
                    id=d["id"],
                    title=d["title"],
                    available=d["active"] and bool(d["text"].strip()),
                    text=d["text"] if d["active"] else "",
                    reason="Active" if d["active"] else "Inactive",
                )
                for d in documents
            ],
            access_lore=lore,
            memories=memories,
            memory_total=total,
            memory_limit=30,
            history=history,
            history_limit=16,
        )
