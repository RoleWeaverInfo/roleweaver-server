# Windows QEMU demo proof of concept

This prototype runs the Linux Role Weaver Demo 1.0.0 inside QEMU on Windows,
using **TCG software emulation**. It does not require WSL2, Hyper-V, Docker,
or an installed Linux VM manager. An installed NWN:EE game client is still needed.

The scripts in this directory are the prototype source. They are not a complete
download by themselves: the assembled local folder also contains QEMU, Linux,
and a prepared guest disk. This is separate from the published Linux releases.

## Try the assembled prototype

1. Open the `RoleWeaver-QEMU-Demo` folder and double-click **Start Demo.cmd**.
2. Use **Check Status.cmd** while the VM starts.
3. Open **Open Dashboard.cmd**, or visit **http://127.0.0.1:8747/**.
   The initial dashboard password is **roleweaver**.
4. In **LLM Service**, configure your provider, model and API key. The prototype
   begins in offline mode; no keys or player memories are imported from another world.
   Translation is enabled by default in new demos. Once a provider is configured,
   players can select a language and turn translation on with `/rw language` in
   Talk. Translations are generated on demand and cached, not prepared in advance.
   Companion AI is also enabled by default. Summon a familiar normally, then use
   `/rw companion on` and `/rw companion settings` in Talk.
   In the updated companion settings, **Local listening** is optional and starts
   off. Enable it before entering the cave, then ask your familiar what it thinks
   after the nearby trolls and hostage speak. It remembers up to eight public
   lines for two minutes; private channels and automatic replies are excluded.
5. In the Windows NWN:EE game, use Multiplayer / Direct Connect:
   **127.0.0.1:5127**. A normal player connection needs no password.
   For a DM connection, launch NWN in DM mode (`-dmc`) and use **roleweaver**.
   For a player connection, launch the normal game without `-dmc`.
6. Use **Stop Demo.cmd** when finished. Wait for shutdown before copying,
   moving or backing up the VM folder.

The dashboard and game ports are available only on this Windows computer.
No SSH tunnel needs to be opened manually. Internet access is still required
for hosted LLM providers. Saved profiles, keys, memories and translations remain
inside `runtime/demo.qcow2` across restarts.

Try movement and conversations in the throne room first, followed by the forest
and cave encounters. Watch for rubber-banding, delayed actions and missed NPC
responses. Software emulation performance must be assessed in actual gameplay;
a healthy dashboard alone does not establish playability.

On the development PC, a prepared VM restart took about **1 minute 47 seconds**
to reach a healthy game bridge and dashboard. This is an observation for that
machine, not a startup-time guarantee for other computers.

## Editable files

The guest is an ordinary Ubuntu installation, with administrator access through
**Open Linux Terminal.cmd**. It is not locked down against your own editing.

- Application/source: `/home/roleweaver/demo`
- Editable source module: `/home/roleweaver/demo/demo/world/YourWorld_Fixed.mod`
- Demo lore and NPC templates: `/home/roleweaver/demo/demo/content.json`
- Active module, overrides, HAKs and TLKs: `/home/roleweaver/demo/.demo/qemu_demo/userdata/`
- Runtime settings: `/home/roleweaver/demo/.demo/qemu_demo/`
- Native server, NWNX and compiler: `/home/roleweaver/native`

Windows `content/modules`, `content/hak` and `content/tlk` folders are staging
folders, not automatic live mounts. Files can be transferred with SFTP using
host `127.0.0.1`, port `12222`, user `roleweaver`, and the private key
`runtime/admin-key`. Stop the guest's game service before replacing active files:

```bash
sudo systemctl stop roleweaver-demo
# Copy or edit the intended files, then:
sudo systemctl start roleweaver-demo
```

The launcher currently runs `YourWorld_Fixed`. Other modules still require their
own Role Weaver hooks, content configuration and module selection; dropping a
different `.mod` file into a folder does not integrate it automatically. The
first prototype tests portability and performance, before adding a module picker.

## Troubleshooting

**"Unable to verify your password"** can refer to NWN's external account
verification, even when the player password is empty. This localhost-only VM
uses `masterserver.key-authentication.mode = "if-reachable"` in its NWN
`userdata/settings.tml`: it checks accounts when the master server is reachable,
and allows local testing during an outage. The DM password is still required.
This is a local demo setting; keep mandatory account verification for a public
server. Your Windows game's settings are not changed.

`logs/serial.log` contains Linux boot output; `logs/qemu-error.log` contains QEMU
startup errors. In the Linux terminal:

```bash
systemctl status roleweaver-demo --no-pager
sudo journalctl -u roleweaver-demo -n 80 --no-pager
```

The dashboard's **Health & Support** panel checks the game bridge and databases.
**Backups** provides application recovery backups. A complete VM backup also
needs the base image under `downloads/ubuntu-minimal.img`: the writable disk is
an overlay, so keep both files together.

## Maintainer notes

- Initial VM allocation: 2 virtual CPUs, 2 GB RAM, 12 GB expandable disk capacity.
  Disk files grow as used; 12 GB is not allocated immediately.
- QEMU uses `-accel tcg,thread=multi`, Q35 with HPET disabled, and direct kernel
  boot with `noapic`. The default APIC timer check failed on this Windows host.
- `runtime/vmlinuz` must match the guest's installed kernel modules. Kernel updates
  need a matching exported kernel; do not treat this as an unattended production image.
- The NoCloud seed is exposed as a virtio block device so it can be discovered
  during initrdless boot. `make-seed.py` generates a seed for a **fresh** image.
- `install-guest.sh` runs only in the new `roleweaver-demo` guest. It installs the
  released demo and optional Guardrails dependencies, prepares the world, and
  enables the guest services and prepares local-demo account verification.
- Dashboard relay: guest TCP 8748 to application loopback TCP 8747. QEMU forwards
  Windows loopback 8747 to the relay, retaining application Host/Origin checks.
- Other forwarded ports: UDP 5127 (game), TCP 12222 (SSH), TCP 18747 (QMP control).
- A guest-only nftables rule fixes this build's localhost UDP forwarding: it
  rewrites incoming game packets from 127.0.0.1 to QEMU's 10.0.2.2 host alias.
  It is scoped to the demo port and loaded by `roleweaver-qemu-network.service`.
  No Windows firewall or network adapter changes are needed.
- A future public image needs fresh per-installation SSH credentials and host
  keys, dependency/source notices, and a clean sealed disk. Do not upload this
  personalized working folder as a release package.

Sources: [QEMU for Windows](https://www.qemu.org/download/#windows),
[Windows QEMU builds](https://qemu.weilnetz.de/w64/),
[Ubuntu Minimal cloud images](https://cloud-images.ubuntu.com/minimal/releases/noble/release-20261001/),
[NoCloud configuration](https://docs.cloud-init.io/en/latest/reference/datasources/nocloud.html).
