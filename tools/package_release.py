"""Build separate demo and existing-server source distributions without runtime data."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
NAMES = {
    "demo": "RoleWeaver-Demo-Alpha-0.1.0",
    "addon": "RoleWeaver-Server-Addon-Alpha-0.1.0",
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
)


def package(output, kind="demo"):
    """Use an explicit source allowlist; fail rather than include private runtime files."""
    guide = "START_DEMO.md" if kind == "demo" else "START_ADDON.md"
    paths = [ROOT / name for name in (*FILES, "START_ADDON.md", guide)]
    for folder in (*FOLDERS, *(("demo",) if kind == "demo" else ())):
        paths.extend(
            p
            for p in (ROOT / folder).rglob("*")
            if p.is_file()
            and not p.is_symlink()
            and "__pycache__" not in p.parts
            and p.name != "nwnsc"
            and p.suffix not in (".pyc", ".sqlite3", ".log")
        )
    if kind == "addon":
        paths = [
            p
            for p in paths
            if p.name
            not in ("test_demo.py", "test_distributions.py", "package_demo.py")
        ]
    forbidden = {
        "provider.env",
        "llm-settings.json",
        "identity_salt",
        "settings.json",
        "new-server.env",
    }
    if any(
        p.name in forbidden or (kind == "addon" and p.suffix == ".mod") for p in paths
    ):
        raise ValueError(
            "Private runtime or unexpected module file detected in package input"
        )
    contents = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
    if kind == "addon":
        contents["addon/example-world/YourWorld_Fixed.mod"] = (
            ROOT / "demo/world/YourWorld_Fixed.mod"
        ).read_bytes()
        contents["addon/example-world/content.json"] = (
            ROOT / "demo/content.json"
        ).read_bytes()
    contents["START_HERE.md"] = contents[guide]
    contents["README.md"] = (
        f"# {NAMES[kind]}\n\nStart with [START_HERE.md](START_HERE.md).\n\n"
        + (
            "Includes an editable demonstration world and playtests in demo/. NWN, NWNX and the compiler are supplied separately.\n"
            if kind == "demo"
            else "For existing NWN/NWNX servers. Your module stays in its existing location. Prepare and review bridge hooks before installing them; this package does not replace or start your game server.\n"
        )
        + "\nSource development: [CONTRIBUTING.md](CONTRIBUTING.md).\n"
    ).encode()
    contents["docs/README.md"] = (
        "# Documentation\n\n- [Start here](../START_HERE.md)\n"
        + "".join(
            f'- [{p.stem.replace("_", " ").title()}]({p.name})\n'
            for p in sorted((ROOT / "docs").glob("*.md"))
            if p.name != "README.md"
        )
    ).encode()
    manifest = {
        name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(contents.items())
    }
    contents["MANIFEST.sha256.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as archive:
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
