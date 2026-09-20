"""Install login/logout wrappers while retaining the world's existing handlers."""

from collections import OrderedDict


def install(module):
    fields = module[1]
    variables = fields.setdefault("VarTable", (15, []))[1]
    for field, wrapper, saved in (
        ("Mod_OnClientEntr", b"rq_enter", b"rq_previous_enter"),
        ("Mod_OnClientLeav", b"rq_exit", b"rq_previous_exit"),
    ):
        old = fields.get(field, (11, b""))[1]
        if old == wrapper:
            continue
        if old in (b"rq_enter", b"rq_exit"):
            raise ValueError("Unexpected crossed investigation session hook")
        matches = [v for v in variables if v[1].get("Name", (None, None))[1] == saved]
        if matches:
            raise ValueError("Existing saved event metadata needs review")
        variables.append(
            (
                0,
                OrderedDict(
                    [("Name", (10, saved)), ("Type", (4, 3)), ("Value", (10, old))]
                ),
            )
        )
        fields[field] = (11, wrapper)
