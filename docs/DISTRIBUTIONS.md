# Alpha 0.3.0 distributions

| Download | Audience |
| --- | --- |
| RoleWeaver-Demo-Alpha-0.3.0.tar.gz | Players/testers using the supplied separate world |
| RoleWeaver-Server-Addon-Alpha-0.3.0.tar.gz | Owners integrating an existing NWN/NWNX world |

Each archive has its own **START_HERE.md**, **README.md**, **RELEASE_NOTES.md** and
**RELEASE.json** (distribution 0.3.0 / runtime 0.28.0). Run `bash setup.sh` from
the extracted folder. The demo includes its launcher and optional playtests; the
add-on prepares bridge resources without requiring a module path or starting NWN.

Both include the edited **YourWorld_Fixed.mod**: `demo/world/` in the demo and
`addon/example-world/` in the add-on. Only managed bridge scripts/resources were
refreshed for this alpha; the owner's layout and investigation hooks are preserved.
The add-on example uses `my_world` / `roleweaver:my_world`. It is an optional
example, not an automatic replacement for an established world. Custom world IDs
need matching compiled bridge settings. See its content.json for authoring data.

NWN, NWNX, Redis, the compiler and the optional compiled translation adapter are
not bundled. Native adapter source and instructions are included in both archives.
Use a matching Linux x86-64 8193.37-17 installation for that adapter.

## Build and inspect

From the source repository, with Python 3.12:

```bash
python3 tools/package_release.py --kind all
```

The archives and their `.sha256` sidecars are generated in **dist/** (ignored by
Git). Each archive contains **MANIFEST.sha256.json** with every other file's hash.
The archive top-level folder matches its filename. Shell launchers have executable
permissions. Gzip/tar metadata is fixed so unchanged input produces identical bytes.
The packager rejects private runtime files, unreviewed binaries and extra modules.

Verify the downloaded files on Linux before extracting:

```bash
sha256sum -c RoleWeaver-Demo-Alpha-0.3.0.tar.gz.sha256
sha256sum -c RoleWeaver-Server-Addon-Alpha-0.3.0.tar.gz.sha256
```

Run only the line for the download you selected. Keep archives and sidecars in
the same folder. SHA-256 detects a mismatched download; obtain both from the
project's release rather than treating the hash alone as proof of origin.

## Publication is separate

Review [release notes](releases/alpha-0.3.0.md), the
[checklist](ALPHA_CHECKLIST.md) and [asset notes](../THIRD_PARTY_NOTICES.md).
Commit the reviewed source and generated example module before tagging
`v0.3.0-alpha.1`. Rebuild from that source, verify the archives, and upload both
archives with their sidecars to a GitHub **prerelease**. Update the repository
README's prepared-release notice only after publication succeeds.

Never upload `.demo/`, runtime databases, credentials, backups or raw logs.
The module-copy builder is optional developer tooling; existing-server installation
keeps the user's module in its own location. A future developer distribution and
the larger version 1 demo are separate work.
