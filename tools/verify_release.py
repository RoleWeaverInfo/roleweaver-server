"""Verify Role Weaver release archives before they are published."""

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts


def verify_sidecar(path):
    sidecar = path.with_name(path.name + ".sha256")
    if not sidecar.is_file():
        raise ValueError(f"Missing checksum: {sidecar.name}")
    fields = sidecar.read_text(encoding="ascii").strip().split()
    if len(fields) != 2 or fields[1] != path.name:
        raise ValueError(f"Invalid checksum record: {sidecar.name}")
    if fields[0].lower() != digest(path.read_bytes()):
        raise ValueError(f"Checksum mismatch: {path.name}")


def inspect_addon(raw):
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        members = archive.getmembers()
        if any(not safe_name(member.name) for member in members):
            raise ValueError("Server Add-on contains an unsafe path")
        if any(member.issym() or member.islnk() for member in members):
            raise ValueError("Server Add-on must not contain links")
        files = {
            member.name: archive.extractfile(member).read()
            for member in members
            if member.isfile()
        }
    roots = {PurePosixPath(name).parts[0] for name in files}
    if len(roots) != 1:
        raise ValueError("Server Add-on must contain one top-level folder")
    root = roots.pop()
    required = {
        f"{root}/setup.sh",
        f"{root}/tools/setup_gui.py",
        f"{root}/tools/setup_wizard.py",
        f"{root}/RELEASE.json",
        f"{root}/MANIFEST.sha256.json",
    }
    missing = required - files.keys()
    if missing:
        raise ValueError("Server Add-on is missing: " + ", ".join(sorted(missing)))
    release = json.loads(files[f"{root}/RELEASE.json"])
    version = release.get("version")
    if release.get("kind") != "addon" or root != f"RoleWeaver-Server-Addon-{version}":
        raise ValueError("Server Add-on name and release metadata disagree")
    manifest = json.loads(files[f"{root}/MANIFEST.sha256.json"])
    content = {
        name[len(root) + 1 :]: value
        for name, value in files.items()
        if name != f"{root}/MANIFEST.sha256.json"
    }
    if set(manifest) != set(content):
        raise ValueError("Server Add-on manifest file list does not match the archive")
    for name, expected in manifest.items():
        if digest(content[name]) != expected:
            raise ValueError(f"Server Add-on manifest mismatch: {name}")
    return version


def verify_addon(path):
    verify_sidecar(path)
    return inspect_addon(path.read_bytes())


def verify_installer(path, addon, version):
    verify_sidecar(path)
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        expected_addon = f"RoleWeaver-Server-Addon-{version}.tar.gz"
        required = {
            "Role Weaver Remote Installer.exe",
            "README.txt",
            expected_addon,
            expected_addon + ".sha256",
        }
        missing = required - names
        if missing:
            raise ValueError(
                "Remote Installer is missing: " + ", ".join(sorted(missing))
            )
        if any(not safe_name(name) or "/" in name for name in names):
            raise ValueError("Remote Installer ZIP must contain only top-level files")
        embedded = archive.read(expected_addon)
        if embedded != addon.read_bytes():
            raise ValueError("Remote Installer contains a different Server Add-on")
        fields = archive.read(expected_addon + ".sha256").decode("ascii").split()
        if len(fields) != 2 or fields[0].lower() != digest(embedded):
            raise ValueError("Bundled Server Add-on checksum is invalid")
        if not archive.read("Role Weaver Remote Installer.exe").startswith(b"MZ"):
            raise ValueError("Remote Installer executable is invalid")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addon", type=Path, required=True)
    parser.add_argument("--installer", type=Path)
    args = parser.parse_args()
    version = verify_addon(args.addon)
    if args.installer:
        verify_installer(args.installer, args.addon, version)
    print(f"Verified Role Weaver {version} release packages")


if __name__ == "__main__":
    main()
