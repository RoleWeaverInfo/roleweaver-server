# Two separate alpha downloads

| Download | Audience |
| --- | --- |
| RoleWeaver-Demo-Alpha-0.1.0.tar.gz | Players/testers using the supplied separate world |
| RoleWeaver-Server-Addon-Alpha-0.1.0.tar.gz | Owners integrating an existing NWN/NWNX world |

Each archive has its own START_HERE.md and README. Both include the edited YourWorld_Fixed.mod: under demo/world/ in the demo and addon/example-world/ in the add-on. The add-on copy is an optional example with authoring content, not an automatic replacement for an existing world. The add-on has no demo launcher and prepares bridge resources without requiring a module path. The source repository retains both authoring trees.

```bash
python tools/package_release.py --kind all
```

Archives, manifests and SHA-256 sidecars are generated in dist/. Upload archives/sidecars as GitHub
prerelease assets after pushing source; dist/ is ignored by Git. Never upload local runtime data,
credentials or raw logs. The legacy module-copy builder remains optional developer tooling, not the
existing-server installation workflow.
