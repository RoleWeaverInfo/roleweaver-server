# Demo alpha validation

Built from Role Weaver runtime 0.26.7 and the modular source baseline.

- Automated unit tests cover content validation, native-source injection rejection, duplicate IDs,
  non-finite coordinates, non-destructive template reapplication, existing-instance refusal,
  native dependency checks, instance locking and compile-failure preservation.
- On the existing Ubuntu test VM, the archived source compiled YourWorld and all bridge/demo scripts
  using that machine's compatible dedicated server, NWNX plugins/headers and compiler.
- An isolated demo on UDP 5126 / dashboard 8746 registered Mira, Orren and Elara in auto mode.
  The action bridge and merchant panel reported ready, with one merchant.
- Stop, rebuild, content import (with database backup) and restart were exercised successfully.
- The foreground runner stopped its own game and dashboard; the established test services were unchanged.

This is not a clean-machine dependency installation test or a completed player/DM playtest of the new
archive. Follow PLAYTEST.md before promoting the archive beyond alpha. Model/Guardrails comparison
results are intentionally left for testers; no model ranking or universal safety guarantee is claimed.
