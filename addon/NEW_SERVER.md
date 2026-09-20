# Set up a new Linux game server

Skip this guide if NWN and NWNX already run your world. Use Ubuntu 24.04 x86-64 for the reference setup. No Docker is required. The Role Weaver add-on is a separate companion; the game server and NWNX binaries are installed separately.

## 1. Download three matching archives

- Get the Linux dedicated server from [Beamdog downloads](https://nwn.beamdog.net/downloads/).
- Get **NWNX-EE.zip** (plugins) and **NWScript.zip** (script headers) from the same compatible [NWNX release](https://github.com/nwnxee/unified/releases). The GitHub Source code ZIP is not the plugin build.

Our tested reference pair is dedicated server **8193.37-17** and NWNX **8193.37.17**. If using another release, check its stated server compatibility; do not mix script headers from one NWNX build with plugins from another. Put the downloads in Ubuntu's Downloads folder.

## 2. Extract into these folders

| Folder | Must contain |
| --- | --- |
| `~/nwserver` | `bin/linux-x86/nwserver-linux` and the runtime `data` directory |
| `~/nwnx/plugins` | `NWNX_Core.so`, `NWNX_Chat.so`, `NWNX_Events.so`, `NWNX_Redis.so`, `NWNX_Creature.so`, `NWNX_Player.so` |
| `~/nwnx/nwscripts` | `nwnx_core.nss`, the other `nwnx_*.nss` files from NWScript.zip |

Use Ubuntu's archive manager to extract the archives. If it creates an extra enclosing folder, move its contents so the paths match this table. Keep the plugin and script-header folders separate.

Install prerequisites and start Redis:

```bash
sudo apt update
sudo apt install python3-venv redis-server unzip
sudo systemctl enable --now redis-server
chmod +x "$HOME/nwserver/bin/linux-x86/nwserver-linux"
```

## 3. Add your module

In Ubuntu Files, create `nwn-world` in your home folder and create a `modules` folder inside it. Copy your own `.mod` there. For example: `~/nwn-world/modules/YourWorld.mod`.

Create `hak` and `tlk` folders inside nwn-world for any custom content your module needs. Copy the required HAK/TLK files there; players need compatible client-side content too. For a first test, a small standard-tileset module is easiest.

The optional `addon/example-world/YourWorld_Fixed.mod` is already integrated and needs its accompanying profiles/lore to demonstrate the full story. Use the Demo distribution for that complete experience. These new-server instructions are for your own module.

## 4. Edit the supplied launcher settings

Extract the Role Weaver add-on package. Inside **addon**, copy **new-server.env.example** to **new-server.env**. Open the copy in a text editor.

Set MODULE_NAME to your filename WITHOUT `.mod`. Set a private DM_PASSWORD, and check the paths, game port and Redis port. The default values match this guide. Keep this file private; it is not part of the release download.

Open a terminal in the extracted package and run:

```bash
bash addon/start-new-server.sh
```

Leave the terminal open. Confirm the module and all six NWNX plugins loaded. Connect from NWN to **UBUNTU-IP:5121** (or your selected port). Run `hostname -I` in another Ubuntu terminal for the IP. Allow the game UDP port through your firewall for your client. A VPN or VM network mode can affect access.

If the log says a library cannot be preloaded, check the underscore in NWNX_Core.so and the plugin path. `ldd ~/nwnx/plugins/NWNX_Core.so` identifies missing shared libraries. A functioning game alone does not mean NWNX loaded.

This is a private test launcher using local player characters. Configure your own production server-vault, passwords, routing and operational policies before public hosting.

## 5. Add Role Weaver

When ordinary player and DM connections work, enter `quit` in the foreground game console and wait for NWN to stop. Return to [START_HERE](../START_HERE.md) in a release download, or [START_ADDON](../START_ADDON.md) in the source repository, and follow steps 1–6.

Use `bash addon/start-new-server.sh` whenever those instructions ask you to start your new test game server. Use `bash addon/setup.sh restart` to restart only the AI companion.
