"""Assemble a fresh portable folder; never export a running/private VM's disk."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

SOURCE = Path(__file__).resolve().parent


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        "--base", required=True, type=Path, help="Sealed, flattened factory image"
    )
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--qemu", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--zip", action="store_true")
    args = parser.parse_args()
    destination = args.output.resolve()
    if destination.exists():
        parser.error(
            "Output must be a new directory; existing installations are never overwritten"
        )
    info = json.loads(
        subprocess.check_output(
            [str(args.qemu / "qemu-img.exe"), "info", "--output=json", str(args.base)]
        )
    )
    if info.get("backing-filename") or info.get("format") != "qcow2":
        parser.error(
            "The factory image must be a standalone QCOW2 with no backing image"
        )
    (destination / "runtime").mkdir(parents=True)
    shutil.copytree(args.qemu, destination / "runtime/qemu")
    shutil.copy2(args.base, destination / "runtime/base.qcow2")
    shutil.copy2(args.kernel, destination / "runtime/vmlinuz")
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SOURCE / "build-launcher.ps1"),
            "-OutputDirectory",
            str(destination),
        ],
        check=True,
    )
    shutil.copy2(SOURCE / "START_HERE.txt", destination / "START_HERE.txt")
    for name in ("modules", "hak", "tlk"):
        (destination / "content" / name).mkdir(parents=True)
    shutil.copy2(SOURCE / "CONTENT_READ_ME.txt", destination / "content/READ_ME.txt")
    shutil.copy2(SOURCE.parent / "LICENSE", destination / "LICENSE")
    shutil.copy2(SOURCE / "THIRD_PARTY.txt", destination / "THIRD_PARTY.txt")
    # Include launcher sources so this executable can be inspected and rebuilt.
    shutil.copytree(SOURCE / "launcher", destination / "launcher-source")
    manifest = dict(
        version="1.0.0",
        source_revision=args.source_revision,
        emulation="QEMU TCG",
        default_dashboard_password="roleweaver",
        default_dm_password="roleweaver",
        files={},
    )
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            manifest["files"][path.relative_to(destination).as_posix()] = digest(path)
    (destination / "BUILD-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    if args.zip:
        archive = destination.parent / (destination.name + ".zip")
        if archive.exists():
            parser.error("The output ZIP already exists")
        with zipfile.ZipFile(
            archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as output:
            for path in sorted(destination.rglob("*")):
                output.write(
                    path, Path(destination.name) / path.relative_to(destination)
                )
        archive.with_suffix(".zip.sha256").write_text(
            digest(archive) + "  " + archive.name + "\n"
        )
        print(archive)
    print(destination)


if __name__ == "__main__":
    main()
