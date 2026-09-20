# Install or link the demo dependencies

Follow this guide **inside Ubuntu 24.04 x86-64**, including when Ubuntu runs in a VM. No Docker is needed. The NWN game client can remain on Windows.

`$HOME` means your Ubuntu home folder. For username `roleweaver`, it is `/home/roleweaver`. Do not substitute a Windows path into these commands.

## Choose your starting point

- **I do not have a dedicated server, NWNX or compiler:** follow **A**, then **C**, then **D**.
- **I already have some or all of them installed:** follow **B**, then **C**, then **D**. You can reuse your installations without moving them.

The demo needs the Linux **dedicated server**, not just the NWN game client. It uses its own module and saved-data folder; it does not load your production world.

## A. Install dependencies from scratch

Skip this section if you already have them. These commands use new dependency folders. If `~/nwserver` or `~/nwnx` already contains an installation, use section B rather than mixing builds into it.

### A1. Install Ubuntu tools and Redis

Open an Ubuntu terminal. These commands can run from any folder:

```bash
sudo apt update
sudo apt install python3-venv redis-server redis-tools curl unzip
sudo systemctl enable --now redis-server
redis-cli -h 127.0.0.1 -p 6379 ping
```

The final command should print **PONG**. Keep Redis on localhost. Do not alter an existing shared Redis service to remove its authentication: this demo requires a compatible unauthenticated loopback endpoint.

### A2. Download the dedicated server and matching NWNX files

The reference setup uses dedicated server **8193.37-17** and NWNX **build8193.37.17-HEAD**. Download the server from [Beamdog](https://nwn.beamdog.net/downloads/) and plugins/headers from the [matching NWNX release](https://github.com/nwnxee/unified/releases/tag/build8193.37.17-HEAD). The NWNX `latest` download changes over time; do not mix builds.

These commands download that reference set into a new folder under Downloads:

```bash
mkdir -p "$HOME/Downloads/roleweaver-deps"
cd "$HOME/Downloads/roleweaver-deps"

curl -fL -o nwnee-dedicated-8193.37-17.zip https://nwn.beamdog.net/downloads/nwnee-dedicated-8193.37-17.zip
curl -fL -o NWNX-EE.zip https://github.com/nwnxee/unified/releases/download/build8193.37.17-HEAD/NWNX-EE.zip
curl -fL -o NWScript.zip https://github.com/nwnxee/unified/releases/download/build8193.37.17-HEAD/NWScript.zip
```

Wait for each download to finish. If a command reports an HTTP error, stop and check the official download page. You can also download these same three files in a browser and put them in this Ubuntu folder. GitHub's **Source code** ZIP is not the plugin package.

### A3. Extract the files

```bash
mkdir -p "$HOME/nwserver" "$HOME/nwnx/plugins" "$HOME/nwnx/nwscripts"
unzip -n "$HOME/Downloads/roleweaver-deps/nwnee-dedicated-8193.37-17.zip" -d "$HOME/nwserver"
unzip -n "$HOME/Downloads/roleweaver-deps/NWNX-EE.zip" -d "$HOME/nwnx/plugins"
unzip -n "$HOME/Downloads/roleweaver-deps/NWScript.zip" -d "$HOME/nwnx/nwscripts"
chmod +x "$HOME/nwserver/bin/linux-x86/nwserver-linux"
```

Check the resulting paths:

```bash
ls "$HOME/nwserver/bin/linux-x86/nwserver-linux"
ls "$HOME/nwnx/plugins/NWNX_Core.so"
ls "$HOME/nwnx/nwscripts/nwnx_core.nss"
```

Each command must print a filename, not “No such file or directory.” If an archive created an extra enclosing folder, open it in Ubuntu Files and move its contents into the intended folder. The plugin filename is **NWNX_Core.so**, with an underscore.

### A4. Install the script compiler

The demo uses **nwnsc** to build its scripts. Download the Linux compiler from the [official nwnsc release](https://github.com/nwneetools/nwnsc/releases/tag/v1.1.5), not the Windows or Mac version:

```bash
curl -fL -o "$HOME/Downloads/roleweaver-deps/nwnsc-linux-v1.1.5.zip" https://github.com/nwneetools/nwnsc/releases/download/v1.1.5/nwnsc-linux-v1.1.5.zip
mkdir -p "$HOME/bin"
unzip -n "$HOME/Downloads/roleweaver-deps/nwnsc-linux-v1.1.5.zip" -d "$HOME/bin"
chmod +x "$HOME/bin/nwnsc"
ls -l "$HOME/bin/nwnsc"
```

The compiler is now at **~/bin/nwnsc**. Continue to **C**; you do not need section B.

## B. Reuse an existing installation

Do not move your server or change its launcher. Identify these four paths:

| Needed path | How to identify it | Common example |
| --- | --- | --- |
| Dedicated server root | Contains BOTH `bin/linux-x86/nwserver-linux` and `data/` | `~/nwserver` |
| NWNX plugin folder | Directly contains `NWNX_Core.so` and the other `.so` files | `~/nwnx/plugins` or `~/nwnxee/Binaries` |
| NWNX script-header folder | Directly contains `nwnx_core.nss` and the other headers | `~/nwnx/nwscripts` |
| Compiler executable | The Linux file named `nwnsc` | `~/bin/nwnsc` |

Use Ubuntu Files to locate the files if needed. The plugin folder and header folder can be in completely different locations. If all your NWNX files are directly in `~/nwnx`, use that path for the appropriate link; do not add `/plugins` or `/nwscripts` unless those folders actually exist.

Required plugins: **Core, Chat, Events, Redis, Creature, Player**. Required headers come from the **NWScript.zip matching your installed NWNX build**, including dependencies such as `nwnx_redis_lib.nss`. If you have plugins but no headers, obtain NWScript.zip from that same release and extract it into a separate header folder.

If the compiler is missing, follow **A4** (create the Downloads/roleweaver-deps folder first). If Redis/Python prerequisites are missing, follow **A1**. If using another Redis port, add `--redis-port YOUR_PORT` to the setup command in D.

## C. Create the demo dependency links

`--native` does NOT mean “the NWN server folder” or “the NWNX folder.” It means a small folder that brings three locations together:

```text
~/nwn-demo-deps/
  runtime   -> your dedicated server root
  plugins   -> your NWNX .so folder
  nwscripts -> your matching NWNX .nss folder
```

These are symbolic links: pointers to your existing folders. They do not copy or relocate the files. Keep the original folders in place.

### C1. For the standard locations in section A

Run once, from any Ubuntu terminal:

```bash
mkdir -p "$HOME/nwn-demo-deps"
ln -s "$HOME/nwserver" "$HOME/nwn-demo-deps/runtime"
ln -s "$HOME/nwnx/plugins" "$HOME/nwn-demo-deps/plugins"
ln -s "$HOME/nwnx/nwscripts" "$HOME/nwn-demo-deps/nwscripts"
```

### C2. If your files are somewhere else

Use C1, but change the **first path** after `ln -s` to your actual folder. The second path is the new link name and stays the same.

For example, if your plugin files are in `~/nwnxee/Binaries`, use this INSTEAD of the plugins line in C1:

```bash
ln -s "$HOME/nwnxee/Binaries" "$HOME/nwn-demo-deps/plugins"
```

For a path containing spaces, keep quotation marks around it. The runtime link must point to the server ROOT, not its `bin/linux-x86` subfolder.

If `ln` reports **File exists**, a link or folder with that name is already present. Do not delete your installation. Inspect the existing links with `ls -l "$HOME/nwn-demo-deps"` and run the checks below. If they point somewhere wrong, you can create a new dependency folder such as `nwn-demo-deps-02`, repeat C1 using that new name, and use it in D.

### C3. Verify that the links work

```bash
ls "$HOME/nwn-demo-deps/runtime/bin/linux-x86/nwserver-linux"
ls "$HOME/nwn-demo-deps/runtime/data/"*.key
ls "$HOME/nwn-demo-deps/runtime/data/"*.bif
ls "$HOME/nwn-demo-deps/plugins/NWNX_Core.so"
ls "$HOME/nwn-demo-deps/plugins/NWNX_Chat.so"
ls "$HOME/nwn-demo-deps/plugins/NWNX_Events.so"
ls "$HOME/nwn-demo-deps/plugins/NWNX_Redis.so"
ls "$HOME/nwn-demo-deps/plugins/NWNX_Creature.so"
ls "$HOME/nwn-demo-deps/plugins/NWNX_Player.so"
ls "$HOME/nwn-demo-deps/nwscripts/nwnx_core.nss"
ls "$HOME/nwn-demo-deps/nwscripts/nwnx_redis_lib.nss"
```

All must find files. A link can be created successfully even when its target does not exist, which is why this check matters. Stop and correct missing paths before setup.

## D. Return to the extracted demo package

Open the extracted **RoleWeaver-Demo-Alpha-0.1.0** folder in Ubuntu Files, right-click empty space, and choose **Open in Terminal**. This matters: the following commands must run in the package folder, not in Downloads/roleweaver-deps or nwn-demo-deps.

If you have not already created its Python environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-guardrails.txt
```

Then prepare the demo:

```bash
.venv/bin/python demo/demo.py setup --native "$HOME/nwn-demo-deps" --compiler "$HOME/bin/nwnsc" --guardrails
```

Change `--native` only if you chose a different LINKS folder. Change `--compiler` if your compiler is somewhere other than `~/bin/nwnsc`; it points to the executable file, not a folder.

After setup reports success:

```bash
.venv/bin/python demo/demo.py start
```

Continue with **Step 4 of START_HERE.md** for connecting to the game and dashboard. If setup previously completed, do not repeat it to restart: use `start`. For intentional changes to a prepared instance, see [CUSTOMIZE.md](CUSTOMIZE.md).

## Common dependency errors

| Error | Check |
| --- | --- |
| Missing runtime/bin/linux-x86/nwserver-linux | The runtime link must point at the dedicated server root. |
| Missing nwnx header | Extract the full matching NWScript.zip; plugin binaries are not headers. |
| Compiler missing/not executable | Check the --compiler filename; run chmod +x on that executable. |
| tools/nwnsc points to a different compiler | The package already has a compiler link from an earlier setup. Use that same compiler or deliberately correct that link while the demo is stopped; the installer will not silently replace it. |
| Shared library missing | Run `ldd` on the named binary/plugin and resolve the reported missing library. File presence alone does not establish compatibility. |
| Exec format error | Use Linux x86-64 binaries. ARM/Mac/Windows binaries do not work in this reference setup. |
| Redis connection failed | Confirm `redis-cli -h 127.0.0.1 -p 6379 ping` prints PONG and setup uses that port. |

NWN binaries and dependency installations stay where you put them. The demo stores its game data and companion settings under `.demo/rw_demo/` in the extracted package; setup also creates a compiler link at `tools/nwnsc` if absent.
