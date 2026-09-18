# Two separate alpha downloads

| Download | Audience |
| --- | --- |
| RoleWeaver-Demo-Alpha-0.1.0.tar.gz | Players/testers using the supplied separate world |
| RoleWeaver-Server-Addon-Alpha-0.1.0.tar.gz | Owners integrating an existing NWN/NWNX world |

Each archive has its own START_HERE.md and README. The add-on contains no .mod file, demo content or
demo launcher. It prepares bridge resources without requiring a module path; existing tooling stays
in charge. The source repository retains both authoring trees.

```bash
python tools/package_release.py --kind all
```

Archives, manifests and SHA-256 sidecars are generated in dist/. Upload archives/sidecars as GitHub
prerelease assets after pushing source; dist/ is ignored by Git. Never upload local runtime data,
credentials or raw logs. The legacy module-copy builder remains optional developer tooling, not the
existing-server installation workflow.
