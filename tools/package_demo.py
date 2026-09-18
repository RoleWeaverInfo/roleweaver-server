"""Package only distributable source/demo inputs, never a tester's runtime or keys."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = (
    "roleweaver",
    "bridge",
    "tools",
    "tests",
    "assets",
    "docs",
    "examples",
    "packaging",
    "demo",
)
FILES = (
    "README.md",
    "START_DEMO.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "config.example.json",
    "requirements-guardrails.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "start-roleweaver.sh",
)


def package(output):
    paths = [ROOT / name for name in FILES]
    for folder in FOLDERS:
        paths += [
            p
            for p in (ROOT / folder).rglob("*")
            if p.is_file()
            and not p.is_symlink()
            and "__pycache__" not in p.parts
            and p.name != "nwnsc"
            and p.suffix not in (".pyc", ".sqlite3", ".log")
        ]
    forbidden = {"provider.env", "llm-settings.json", "identity_salt", "settings.json"}
    if any(p.name in forbidden for p in paths):
        raise ValueError("Private runtime file detected in package input")
    root = "RoleWeaver-Demo-Alpha-0.1.0"
    manifest = {
        str(p.relative_to(ROOT))
        .replace("\\", "/"): hashlib.sha256(p.read_bytes())
        .hexdigest()
        for p in paths
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as archive:
        for p in sorted(paths):
            info = archive.gettarinfo(
                str(p), arcname=root + "/" + str(p.relative_to(ROOT)).replace("\\", "/")
            )
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o755 if p.suffix == ".sh" else 0o644
            with p.open("rb") as source:
                archive.addfile(info, source)
        raw = (json.dumps(manifest, indent=2) + "\n").encode()
        info = tarfile.TarInfo(root + "/MANIFEST.sha256.json")
        info.size = len(raw)
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(raw))
    output.with_suffix(output.suffix + ".sha256").write_text(
        hashlib.sha256(output.read_bytes()).hexdigest() + "  " + output.name + "\n"
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "dist/RoleWeaver-Demo-Alpha-0.1.0.tar.gz"
    )
    args = parser.parse_args()
    package(args.output)
    print(args.output)
