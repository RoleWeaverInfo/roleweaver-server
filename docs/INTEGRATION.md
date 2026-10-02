# Optional module-copy builder

For an existing world, use [START_ADDON.md](../START_ADDON.md). Guided setup keeps
your module in its own folder. See [module hooks](../addon/INTEGRATION.md) for the
required game integration.

`tools/build_addon.py` is a separate advanced workflow generating a review bundle
and patched **copy** of a module. Demo build tooling also uses it.
It is not a prerequisite for the existing-server wizard.

From the package/source root:

```bash
.venv/bin/python tools/build_addon.py --help
```

Supply a module, matching runtime/NWNX headers, compiler, world ID, Redis prefix
and new output folder as described by its arguments. Review the audit, generated
INSTALL.md and manifest. Preserve existing handlers, filtering and resource
precedence; static inspection cannot prove compatibility with custom frameworks.

Do not write output into a live world's folders. An already-integrated module may
need an update workflow rather than generic wrapper insertion. The demo's
`rebuild` command handles its own story hooks and current bridge resources.
