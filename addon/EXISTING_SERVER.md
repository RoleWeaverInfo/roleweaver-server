# Existing NWN/NWNX servers

Start with [START_ADDON.md](../START_ADDON.md), steps 1–6. The editable addon/setup.json and addon/setup.sh replace the older long command examples.

Keep your existing launcher, module path, plugin configuration, backups and restart method. Prepare imports against the NWScript headers matching YOUR installed NWNX build. Import into a staging copy first.

For module integration, follow [AURORA.md](AURORA.md), especially the **existing world** event instructions. Custom chat frameworks and build pipelines should also review [INTEGRATION.md](INTEGRATION.md). Preparation does not read/copy your module or overwrite any running server resources.
