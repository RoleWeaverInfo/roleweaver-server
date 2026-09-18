# Modified-world compatibility

The no-module preparer intentionally does not inspect your world. It cannot infer event pipelines,
HAK precedence, chat moderation, creature pooling or custom economies. Review the integration hooks.

- Tested platform: Ubuntu 24.04/Python 3.12 with a compatible Linux dedicated server/NWNX pair.
- Required plugins: Core, Chat, Events, Redis, Creature and Player. Preserve your other plugins.
- Redis: the Python client supports unauthenticated loopback Redis on a configurable port. Remote,
  TLS and authenticated Redis need additional support. Do not weaken an existing secure Redis setup.
- If using a separate local Redis instance, consider that NWNX Redis may already serve other game
  systems: its endpoint cannot be changed independently of those users without review.
- World-owned spawn/persistence is the default; explicitly bind/unbind in existing lifecycle hooks.
- Choose one chat route. Forward only approved public Talk, after moderation and privacy decisions.
- Test Talk To interception/fallback with existing conversation systems.
- Keep merchant features off until store-event and price-script coexistence is tested.
- Dashboard administration is local or through SSH; there is no public multiuser authentication system.
- Native compilation is needed for world-specific settings even when the companion already starts.

Check the [official NWNX compatibility guide](https://github.com/nwnxee/unified/blob/master/README.md).
If you cannot recompile the relevant handlers, ask the world maintainer for hooks rather than replacing
them with demo wrappers or a different module.
