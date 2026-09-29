# Third-party and asset notes

The repository's existing MIT license applies to original Role Weaver code. It does not relicense
Neverwinter Nights, NWNX, Python dependencies or third-party module content.

NWN server binaries/game data, NWNX binaries and compiler tools are external prerequisites and are
not committed here. Dependency licenses remain with their respective projects.

`assets/rw_shop.utm` has a source generator in `tools/build_shop_asset.py`.
`assets/rw_base.utc` is an inherited development blueprint. Its provenance remains
an open review item; inclusion in an earlier alpha does not establish redistribution
rights. `assets/rw_tr_guide.utc` is generated from that blueprint by
`tools/build_translation_demo.py`. The same tool builds `assets/rw_tr_demo.dlg`
from the project's authored `examples/translation_dialogue.json`.

The editable `YourWorld_Fixed.mod` was supplied and edited by the project owner.
It includes inherited module resources/handlers, including DMFI integration.
Preserve existing credits and review applicable third-party permissions before
wider redistribution. Alpha 0.3.0 refreshes only Role Weaver's managed bridge
scripts/resources; it does not establish or change the other assets' licensing.

The creature catalogue contains game-facing identifiers. The dashboard splash
image was supplied by the project owner. Original Role Weaver source, authored
lore and generators remain subject to the repository license; that license does
not grant rights to the underlying game's assets or other third-party content.
