# Rebuilding this prototype

This is a maintainer recipe, not the end-user setup. The portable package contains
a prepared image and native Windows launcher. Never package a private testing
disk. Build a new disposable VM from the verified Ubuntu image and clean archives.

## Inputs

- Windows x86-64 QEMU build, obtained through the QEMU project's Windows download
  link. This prototype used `qemu-w64-setup-20260811.exe` from
  `https://qemu.weilnetz.de/w64/`, verified against its `.sha512` file.
- Ubuntu Minimal 24.04 amd64, build `release-20261001`:
  `https://cloud-images.ubuntu.com/minimal/releases/noble/release-20261001/ubuntu-24.04-minimal-cloudimg-amd64.img`
  (SHA256 `a8eb6570f87a941f3de2e000c046b9367f8ab1423756a94830d454fae8ad80ff`).
  Verify this against that build's `SHA256SUMS` before use.
- Its matching kernel from the same release's `unpacked/` directory,
  `ubuntu-24.04-minimal-cloudimg-amd64-vmlinuz-generic`, SHA256
  `bae162f72d687f8f87909f1dfedea1dfe16adefe40da51f649d9a9b6d498342b`.
- RoleWeaver-Demo-1.0.0.tar.gz, built from the current shared source as below.
  The originally published v1.0.0 archive predates the payment-state bridge fix
  and the enabled demo translation/companion defaults.
- A clean native dependency archive, as described below.
- Python with `pycdlib` to create the first-boot configuration ISO. Python is
  needed by the builder, not by the Windows player using a prepared image.

Build both Linux distributions from the same source checkout before assembling
the VM. From the repository root:

```powershell
python tools/package_release.py --kind all --output-dir dist/qemu-input
```

Use `dist/qemu-input/RoleWeaver-Demo-1.0.0.tar.gz` as the guest's input archive,
and retain its `.sha256` file with the build record. The matching server add-on
archive contains the same application and bridge code. Shared behavior fixes
belong in those sources, not in guest-only provisioning patches. This command
does not update GitHub release assets or upgrade an existing guest installation.

## Assemble the folder

Extract the QEMU executables, DLLs, firmware `share` directory and license files
to `runtime/qemu`. A portable extraction avoids a machine-wide installer. Keep
the QEMU and dependency licenses with the runtime.

Copy the Ubuntu disk to `downloads/ubuntu-minimal.img`, and its kernel to
`runtime/vmlinuz`. Copy this directory's launcher scripts to the prototype root.
Create `logs`, `content/modules`, `content/hak`, and `content/tlk` directories.

From the prototype root, create the private key and writable disk **once**:

```powershell
ssh-keygen -t ed25519 -N '""' -C roleweaver-qemu-local -f runtime/admin-key
python make-seed.py runtime
runtime/qemu/qemu-img.exe create -f qcow2 -F qcow2 -b ../downloads/ubuntu-minimal.img runtime/demo.qcow2 12G
```

Do not overwrite an existing key, seed or guest disk. `make-seed.py` refuses to
replace the seed. The PowerShell quoting shown is for Windows PowerShell 5.1;
PowerShell 7 can pass an empty argument as `-N ""`.

## Native dependencies and guest preparation

The native archive must contain `native/runtime`, `native/plugins`,
`native/nwscripts`, and an executable `native/nwnsc`. Use matching NWN:EE/NWNX
builds; this prototype uses 8193.37-17. Include the following plugins:
Core, Chat, Events, Redis, Creature, Player, Item, Dialog, Util, and RWTranslation.
The game runtime needs `bin`, `data`, `lang`, and `databuild.txt` from the dedicated
server distribution. Include the matching NWNX script headers. Do not import a
world's user directory, launch configuration, API keys, or player data.

Start the VM. Once SSH is ready, transfer `native.tar.gz`, the demo release archive,
and `install-guest.sh` to `/home/roleweaver/`. Use SSH port 12222 and the generated
key. Accept and record the initial host key for this new guest, then use strict
host-key verification for subsequent connections.

Run `bash install-guest.sh` in the guest. It waits for cloud-init, installs Python
dependencies, compiles the bridge, seeds fresh demo data, and enables automatic
startup. This initial build is slow under TCG; normal boots reuse the installed
dependencies and compiled scripts.

Verify dashboard login, the UDP query, the game bridge and clean stop/start before
gameplay testing. Record the resolved Python versions with `pip freeze` and
checksums of the input archives. Keep the base disk and overlay together.

Test **actual player and DM logins**, including the default DM password. A UDP
query only proves that the server answers status requests. The provisioner sets
the new guest's master-server account validation to `if-reachable` for this
localhost-only demo, so an unavailable authentication service does not prevent
testing. Do not carry that setting into a public persistent-world installation.

## Seal a new portable image

Use a separate build VM and distinct forwarded ports if the private demo is
running. The build must never receive real provider keys or player saves.

1. Finish provisioning and check the bundled scripts, dashboard and NWNX bridge.
2. Copy `guest-firstboot.py`, `install-firstboot.sh` and `seal-guest.py` to the
   disposable guest's `/home/roleweaver/`. In that guest only, create
   `/root/roleweaver-disposable-build` containing exactly
   `fresh-public-image-no-player-data`.
3. Run `sudo bash install-firstboot.sh`, then `sudo python3 seal-guest.py`.
   This stops the demo, clears its fresh runtime data/Redis, removes build access
   and host keys, and disables cloud-init. The first Windows launch supplies a
   new public key through QEMU's read-only FAT boot drive. No API key is put there.
4. Run `sudo poweroff`. Wait for QEMU to exit before touching the image.
5. Flatten the stopped build disk using `qemu-img convert -O qcow2 -c` into a
   new `base.qcow2`. Verify `qemu-img info --output=json` has no backing filename.
   Never use the user's private `runtime/demo.qcow2` for this step.
6. Run `package_windows.py --base <base.qcow2> --kernel <vmlinuz> --qemu <qemu-folder>
   --output <new-package-folder> --source-revision <commit> --zip` from Windows
   with Python 3.11+. It refuses to overwrite a folder or use a dependent image.
   The .NET Framework C# compiler builds the splash image directly into the EXE.
7. Test a freshly extracted copy on alternate ports: initial seeding, login,
   provider save/preservation, bridge health, clean shutdown, restart and moving
   the whole stopped folder. Check that another new copy gets a different key
   and identity. Do not include the resulting `userdata/` in the distribution.

Public release review also includes third-party notices, corresponding source
availability and actual player/DM game login. Local launcher/API smoke checks
cannot substitute for a fresh gameplay test on another Windows installation.

Run `test-model-flow.ps1 -OutputDirectory <temporary-folder>` to exercise the
actual WinForms event loop against a local test HTTP endpoint. It checks slow
startup and model-list requests, cancellation, retained input, retry, failed
provider responses and closing the window during a request. It starts no VM,
uses no real key and makes no hosted-provider calls.
