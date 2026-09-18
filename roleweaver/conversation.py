"""World-wide conversation routing settings, independently validated by the game."""

DEFAULTS = dict(
    selection_range=3,
    close_range=6,
    hearing_range=10,
    timeout=180,
    line_of_sight=True,
    direct_address=True,
    follow_hearing=True,
)
LEGACY_KEYS = {
    "close_range",
    "hearing_range",
    "timeout",
    "line_of_sight",
    "direct_address",
}


def settings(value=None):
    if value is None:
        return dict(DEFAULTS)
    if not isinstance(value, dict) or set(value) != set(DEFAULTS):
        raise ValueError("Supply all conversation settings")
    for key, low, high in (
        ("selection_range", 1, 20),
        ("close_range", 1, 20),
        ("hearing_range", 1, 20),
        ("timeout", 15, 300),
    ):
        if type(value[key]) is not int or not low <= value[key] <= high:
            raise ValueError(
                key.replace("_", " ")
                + ": enter a whole number from "
                + str(low)
                + " to "
                + str(high)
            )
    if not value["selection_range"] <= value["close_range"] <= value["hearing_range"]:
        raise ValueError(
            "Talk To distance must not exceed ongoing conversation distance, which must not exceed hearing range"
        )
    for key in ("line_of_sight", "direct_address", "follow_hearing"):
        if type(value[key]) is not bool:
            raise ValueError(key.replace("_", " ") + " must be enabled or disabled")
    return dict(value)


def migrate(value):
    """Keep legacy custom distances/timeouts when loading existing data or old backups."""
    if isinstance(value, dict) and set(value) == LEGACY_KEYS:
        value = dict(value, selection_range=value["close_range"], follow_hearing=False)
    return settings(value)


def wire(value):
    return {k: int(v) for k, v in settings(value).items()}
