"""Compile the bridge and create a separate playable module using installed game data."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from module_copy import make_copy, resources, simple_fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    args = parser.parse_args()
    base = Path(__file__).resolve().parent.parent
    native = args.native.resolve()
    settings = json.loads((native / "server.json").read_text())
    module = native / "userdata/modules" / (settings["module"] + ".mod")
    target = base / "development/userdata/modules/RoleWeaver_Development.mod"
    old = make_copy(module, target)
    fields = simple_fields(
        next(
            data
            for name, kind, data in resources(module.read_bytes())
            if name == "module" and kind == 2014
        )
    )
    area = fields["Mod_Entry_Area"]
    x, y, z = (fields["Mod_Entry_" + axis] for axis in ("X", "Y", "Z"))
    override = base / "development/userdata/override"
    override.mkdir(parents=True, exist_ok=True)
    for path in (base / "bridge").glob("*.nss"):
        (override / path.name).write_bytes(path.read_bytes())
    (override / "rw_shop.utm").write_bytes((base / "assets/rw_shop.utm").read_bytes())
    from build_addon import settings as bridge_settings

    (override / "rw_settings.nss").write_text(
        bridge_settings(
            "roleweaver_development", "roleweaver:v1", "roleweaver", "exclusive"
        )
    )
    wrapper = "void main() {\n"
    if old:
        wrapper += 'ExecuteScript("' + old + '", OBJECT_SELF);\n'
    wrapper += 'ExecuteScript("rw_init", GetModule());\n}\n'
    (override / "rw_load.nss").write_text(wrapper)
    for name in (
        "rw_init",
        "rw_chat",
        "rw_possess",
        "rw_tick",
        "rw_talk",
        "rw_shop_evt",
        "rw_load",
    ):
        subprocess.run(
            [
                str(base / "tools/nwnsc"),
                "-n",
                str(native / "runtime"),
                "-i",
                str(native / "nwscripts") + ";" + str(override),
                str(override / (name + ".nss")),
            ],
            check=True,
            timeout=15,
        )
    # Initial placement is data, not an unconditional game spawn on every reload.
    sys.path.insert(0, str(base))
    from roleweaver.store import Store

    (base / "data").mkdir(mode=0o700, exist_ok=True)
    store = Store(base / "data/roleweaver.sqlite3")
    try:
        if not any(
            p["npc"] == "mira" for p in store.placements("roleweaver_development")
        ):
            area_fields = simple_fields(
                next(
                    data
                    for name, kind, data in resources(module.read_bytes())
                    if name == area and kind == 2012
                )
            )
            store.save_placement(
                dict(
                    npc="mira",
                    world="roleweaver_development",
                    session="installation",
                    area=area,
                    area_tag=area_fields["Tag"],
                    tag="rw_mira",
                    resref="innkeeper",
                    name="Mira",
                    source="spawn",
                    x=x + 2,
                    y=y,
                    z=z,
                    facing=0.0,
                    dead=0,
                )
            )
    finally:
        store.db.close()
    (base / "development/native_path.txt").write_text(str(native))
    config_path = base / "config.json"
    config = json.loads(
        (
            config_path if config_path.exists() else base / "config.example.json"
        ).read_text()
    )
    config.update(placement_owner="roleweaver", redis_prefix="roleweaver:v1")
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    print("Development copy ready. Original module unchanged. Entry area:", area)


if __name__ == "__main__":
    main()
