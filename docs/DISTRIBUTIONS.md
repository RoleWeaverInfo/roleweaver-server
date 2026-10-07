# Version 1.0.1 distributions

| Download | Audience |
| --- | --- |
| RoleWeaver-Server-Addon-1.0.1.tar.gz | Owners installing directly on an existing Linux NWN/NWNX host |
| RoleWeaver-Remote-Installer-1.0.1.zip | Windows administrators connecting to a remote Linux host; includes the matching add-on |
| RoleWeaver-Demo-1.0.0.tar.gz | Existing editable Linux demo, unchanged in this patch release |

The Linux archive has **START_HERE.md**, **README.md**, **RELEASE_NOTES.md** and
**RELEASE.json** (distribution and runtime 1.0.1, stable channel). Run `bash setup.sh`
from the extracted folder. The add-on reads the selected module to generate
path-specific integration instructions while leaving it in place and never starting
NWN. The Windows ZIP has its own README and bundles that exact Linux archive.

The add-on includes the edited **YourWorld_Fixed.mod** in `addon/example-world/`.
The throne room, forest, cave, placed objects and investigation hooks are retained.
The example uses `my_world` / `roleweaver:my_world`. It is an optional
example, not an automatic replacement for an established world. Custom world IDs
need matching compiled bridge settings. See its content.json for authoring data.

NWN, NWNX, Redis, the compiler and the optional compiled translation adapter are
not bundled. Native adapter source and instructions are included in both archives.
Use a matching Linux x86-64 8193.37-17 installation for that adapter.

## Build and inspect

From the source repository, with Python 3.12 and Windows PowerShell for the installer:

```bash
python3 tools/package_release.py --kind addon
powershell -File windows-installer/package.ps1 -AddonArchive dist/RoleWeaver-Server-Addon-1.0.1.tar.gz
```

The archives and their `.sha256` sidecars are generated in **dist/** (ignored by
Git). Each archive contains **MANIFEST.sha256.json** with every other file's hash.
The archive top-level folder matches its filename. Shell launchers have executable
permissions. Gzip/tar metadata is fixed so unchanged input produces identical bytes.
The packager rejects private runtime files, unreviewed JSON/CSV exports, binaries
and extra modules. It also rejects player/history fields in the authored demo seed
and checks relative documentation links against the files actually shipped.

## Clean demo data

The demo is seeded from `demo/content.json`, not exported from a running server.
It retains authored profiles, lore, actions, shops and the two encounter definitions.
First setup creates new databases with no player memories, conversation history,
translation cache or saved player language choices. API keys, dashboard credentials,
identity salts, logs, backups and server character saves are not copied into either
archive. The normal first-run dashboard password remains `roleweaver`; change it
using [Dashboard login](DASHBOARD_LOGIN.md).

This clean starting state applies to a **new demo installation**. Updating an existing
installation deliberately preserves its player data. Packaging does not erase the
development server's databases.

Verify the downloaded files on Linux before extracting:

```bash
sha256sum -c RoleWeaver-Server-Addon-1.0.1.tar.gz.sha256
sha256sum -c RoleWeaver-Remote-Installer-1.0.1.zip.sha256
```

Run only the line for the download you selected. Keep archives and sidecars in
the same folder. SHA-256 detects a mismatched download; obtain both from the
project's release rather than treating the hash alone as proof of origin.

## Publication is separate

Review [release notes](releases/1.0.1.md), the
[checklist](RELEASE_CHECKLIST.md) and [asset notes](../THIRD_PARTY_NOTICES.md).
Commit the reviewed source and generated example module before tagging
`v1.0.1`. Rebuild from that source, verify the archives, and upload both
archives with their sidecars to a normal GitHub release, marked latest and **not**
a prerelease. Verify the public downloads against the locally built checksums.
Forum and Neverwinter Vault announcements are separate from GitHub publication.

Never upload `.demo/`, runtime databases, credentials, backups or raw logs.
The module-copy builder is optional developer tooling; existing-server installation
keeps the user's module in its own location. A future developer distribution and
further demo expansion are separate work. Tagged GitHub source is the developer download for now.
