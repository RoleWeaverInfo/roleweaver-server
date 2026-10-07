"""Build separate demo and existing-server source distributions without runtime data."""

import argparse
import ast
import gzip
import hashlib
import io
import json
from pathlib import Path
import posixpath
import re
import tarfile
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def runtime_version():
    """Read the version without importing the application or its dependencies."""
    tree = ast.parse((ROOT / "roleweaver/__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError("Application runtime version is missing")


VERSION = runtime_version()
NAMES = {
    "demo": f"RoleWeaver-Demo-{VERSION}",
    "addon": f"RoleWeaver-Server-Addon-{VERSION}",
}
# Only these authored binary resources belong in a source distribution. In
# particular, native executables/plugins and copied runtime archives do not.
ASSETS = {
    "assets/rw_base.utc",
    "assets/rw_shop.utm",
    "assets/rw_tr_demo.dlg",
    "assets/rw_tr_guide.utc",
    "demo/world/YourWorld_Fixed.mod",
    "roleweaver/static/rw_server_splash.png",
}
# JSON is not a general documentation format here: unreviewed JSON can contain
# an exported world backup, saved player identity, credentials or test history.
AUTHORED_JSON = {
    "config.example.json",
    "addon/setup.json",
    "demo/content.json",
    "demo/investigation/content.json",
    "examples/translation_dialogue.json",
    "examples/encounters/robbery/profiles.json",
    "examples/encounters/troll-ransom/profiles.json",
    "roleweaver/creature_catalog.json",
    "roleweaver/merchant_catalog.json",
}
SOURCE_SUFFIXES = {
    ".py",
    ".js",
    ".cjs",
    ".html",
    ".nss",
    ".md",
    ".txt",
    ".json",
    ".csv",
    ".service",
    ".sh",
    ".example",
}
PRIVATE_NAMES = {
    "provider.env",
    "llm-settings.json",
    "dashboard-auth.json",
    "identity_salt",
    "settings.json",
    "config.json",
    "new-server.env",
}
RUNTIME_DIRS = {
    "data",
    "builds",
    "native",
    "modules",
    "dist",
    "test-runtime",
    "recovery-backups",
    "update-backups",
    "previous-builds",
}
FOLDERS = (
    "roleweaver",
    "bridge",
    "tools",
    "tests",
    "assets",
    "docs",
    "examples",
    "packaging",
    "addon",
)
FILES = (
    "CONTRIBUTING.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "config.example.json",
    "requirements-guardrails.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "start-roleweaver.sh",
    "setup.sh",
    "extensions/nwnx_translation/CMakeLists.txt",
    "extensions/nwnx_translation/Translation.cpp",
    "extensions/nwnx_translation/TranslationTests.inc",
    "extensions/nwnx_translation/README.md",
)


def source_file(path):
    """Fail closed on runtime/private/unreviewed files, skip Python caches/links."""
    relative = path.relative_to(ROOT)
    if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
        return False
    if any(p.is_symlink() for p in (path, *path.parents) if p != ROOT):
        return False
    if (
        path.name in PRIVATE_NAMES
        or path.name.startswith(".env")
        or any(p.startswith(".") or p in RUNTIME_DIRS for p in relative.parts[:-1])
    ):
        raise ValueError(f"Private runtime file detected in package input: {relative}")
    if path.suffix == ".json" and relative.as_posix() not in AUTHORED_JSON:
        raise ValueError(f"Unreviewed JSON file in package input: {relative}")
    if path.suffix == ".csv" and relative.as_posix() != "demo/results-template.csv":
        raise ValueError(f"Unreviewed CSV file in package input: {relative}")
    if (
        relative.as_posix() not in ASSETS
        and relative.as_posix() not in FILES
        and path.suffix not in SOURCE_SUFFIXES
    ):
        raise ValueError(f"Unreviewed file type in package input: {relative}")
    return True


def validate_demo_content(raw):
    """Distribution seed is authored data, never a dump of a live world store."""
    data = json.loads(raw)
    allowed = {
        "scenario",
        "area_tag",
        "blueprint",
        "npcs",
        "world_documents",
        "access_lore",
        "controlled_actions",
        "merchant_configs",
        "safeguards",
        "conversation",
        "encounters",
    }
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError("Demo content contains unreviewed runtime fields")
    fields = {
        "id",
        "name",
        "role",
        "personality",
        "voice",
        "lore",
        "boundaries",
        "guidance",
        "mode",
        "appearance",
        "race",
        "gender",
        "npc_class",
        "level",
        "factions",
        "area_tag",
        "x",
        "y",
        "z",
        "facing",
        "shop",
        "spawn",
    }
    for npc in data.get("npcs", []):
        if (
            not isinstance(npc, dict)
            or set(npc) - fields
            or str(npc.get("id", "")).startswith("cp_")
        ):
            raise ValueError(
                "Demo seed contains a player companion or unreviewed NPC fields"
            )
    # Encounter definitions, not current participants, rolls or run ledgers.
    for scene in data.get("encounters", []):
        if any(
            key in scene
            for key in ("runs", "participants", "check_results", "receipts", "events")
        ):
            raise ValueError("Demo seed contains encounter runtime state")


def validate_document_links(contents):
    """Check relative Markdown links against the actual archive, not the repo."""
    missing = []
    for name, raw in contents.items():
        if not name.endswith(".md"):
            continue
        text = re.sub(r"```.*?```", "", raw.decode("utf-8"), flags=re.S)
        for match in re.finditer(r"\[[^\]\n]*\]\(([^)\n]+)\)", text):
            target = match[1].strip().strip("<>")
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            path = posixpath.normpath(
                posixpath.join(posixpath.dirname(name), unquote(url.path))
            )
            if path not in contents and not any(
                n.startswith(path.rstrip("/") + "/") for n in contents
            ):
                missing.append(f"{name}: {target}")
    if missing:
        raise ValueError("Broken packaged documentation links:\n" + "\n".join(missing))


def package(output, kind="demo"):
    """Use an explicit source allowlist; fail rather than include private runtime files."""
    if kind not in NAMES:
        raise ValueError("Unknown distribution kind")
    if runtime_version() != VERSION:
        raise ValueError("Application and distribution versions must match")
    validate_demo_content((ROOT / "demo/content.json").read_bytes())
    guide = "START_DEMO.md" if kind == "demo" else "START_ADDON.md"
    paths = [ROOT / name for name in (*FILES, "START_ADDON.md", guide)]
    for folder in (*FOLDERS, *(("demo",) if kind == "demo" else ())):
        paths.extend(
            p for p in (ROOT / folder).rglob("*") if p.is_file() and source_file(p)
        )
    if kind == "addon":
        paths = [
            p
            for p in paths
            if p.name
            not in (
                "test_demo.py",
                "test_demo_cleanup.py",
                "test_distributions.py",
                "package_demo.py",
            )
        ]
    if any(
        not source_file(p) or (kind == "addon" and p.suffix == ".mod") for p in paths
    ):
        raise ValueError(
            "Private runtime or unexpected module file detected in package input"
        )
    contents = {}
    for path in paths:
        name = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes()
        # Windows checkouts may have CRLF despite Git's intended attributes.
        # Linux shell launchers must not ship with CR characters. Normalize only
        # reviewed text files; never touch bytes in the authored binary assets.
        contents[name] = raw if name in ASSETS else raw.replace(b"\r\n", b"\n")
    if kind == "addon":
        contents["addon/example-world/YourWorld_Fixed.mod"] = (
            ROOT / "demo/world/YourWorld_Fixed.mod"
        ).read_bytes()
        contents["addon/example-world/content.json"] = (
            ROOT / "demo/content.json"
        ).read_bytes()
    contents["START_HERE.md"] = contents[guide]
    notes = f"docs/releases/{VERSION}.md"
    contents["RELEASE_NOTES.md"] = contents[notes]
    contents["RELEASE.json"] = (
        json.dumps(
            {
                "distribution": NAMES[kind],
                "version": VERSION,
                "channel": "stable",
                "runtime_version": runtime_version(),
                "kind": kind,
            },
            indent=2,
        )
        + "\n"
    ).encode()
    contents["README.md"] = (
        f"# {NAMES[kind]}\n\nStart with [START_HERE.md](START_HERE.md).\n\n"
        + (
            "Includes an editable demonstration world and playtests in demo/. NWN, NWNX and the compiler are supplied separately.\n"
            if kind == "demo"
            else "For existing NWN/NWNX servers. Your module stays in its existing location. Prepare and review bridge hooks before installing them; this package does not replace or start your game server.\n"
        )
        + "\nSource development: [CONTRIBUTING.md](CONTRIBUTING.md).\n"
        + "\nRead [release notes and limitations](RELEASE_NOTES.md) before upgrading.\n"
    ).encode()
    index = contents["docs/README.md"].decode("utf-8")
    if kind == "addon":
        index = index.replace("- [Demo setup](../START_DEMO.md)\n", "")
    contents["docs/README.md"] = index.replace(
        "# Documentation\n",
        "# Documentation\n\nStart with [START_HERE.md](../START_HERE.md).\n",
        1,
    ).encode()
    validate_document_links(contents)
    manifest = {
        name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(contents.items())
    }
    contents["MANIFEST.sha256.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Stable gzip/tar metadata makes rebuilding the same source reproducible.
    with (
        output.open("wb") as stream,
        gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w") as archive,
    ):
        for name, raw in sorted(contents.items()):
            info = tarfile.TarInfo(NAMES[kind] + "/" + name)
            info.size = len(raw)
            info.mode = 0o755 if name.endswith(".sh") else 0o644
            archive.addfile(info, io.BytesIO(raw))
    output.with_suffix(output.suffix + ".sha256").write_text(
        hashlib.sha256(output.read_bytes()).hexdigest() + "  " + output.name + "\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("demo", "addon", "all"), default="all")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    for kind in (("demo", "addon") if args.kind == "all" else (args.kind,)):
        output = args.output_dir / (NAMES[kind] + ".tar.gz")
        package(output, kind)
        print(output)
