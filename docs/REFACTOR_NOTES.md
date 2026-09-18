# Source organization milestone

Baseline: tested runtime 0.26.7. This milestone preserves the runtime version and makes no intended
protocol or gameplay change. It does not replace the running test installation.

- Extracted dialogue/safeguards, NPC lifecycle and world administration into domain mixins.
- Preserved Service entry points and shared-state cancellation/acknowledgement semantics.
- Formatted Python using Black with AST equivalence checks.
- Relocated guides to docs and updated installer document-copy paths.
- Added architecture, developer setup, contribution conventions and CI.

Further decomposition of the HTTP dispatcher, provider and action coordinator can follow as their
APIs settle. Browser JS and NWScript retain existing structure. Guided demo setup, diagnostic
export and clean-machine installation are separate alpha milestones.
