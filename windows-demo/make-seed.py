"""Create a private NoCloud seed for a fresh QEMU image (requires pycdlib).

Generate admin-key with ssh-keygen first. This file embeds only its PUBLIC key.
Do not change the seed instance ID on an already-configured guest.
"""

import argparse
import io
from pathlib import Path
import uuid

import pycdlib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    args = parser.parse_args()
    output = args.runtime / "seed.iso"
    if output.exists():
        raise SystemExit("Seed already exists; refusing to change this VM's identity.")
    key = (args.runtime / "admin-key.pub").read_text().strip()
    if not key.startswith("ssh-ed25519 ") or "\n" in key:
        raise SystemExit("Expected one ssh-ed25519 public key.")
    user_data = f"""#cloud-config
hostname: roleweaver-demo
manage_etc_hosts: true
users:
  - name: roleweaver
    groups: [sudo]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: true
    ssh_authorized_keys:
      - {key}
ssh_pwauth: false
disable_root: true
package_update: true
package_upgrade: false
packages:
  - python3-venv
  - redis-server
  - socat
  - nftables
  - libstdc++6
  - libcurl4t64
  - ca-certificates
runcmd:
  - [systemctl, enable, --now, redis-server]
  - [touch, /home/roleweaver/cloud-ready]
"""
    metadata = f"instance-id: rw-qemu-{uuid.uuid4()}\nlocal-hostname: roleweaver-demo\n"
    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=3, joliet=3, rock_ridge="1.09", vol_ident="CIDATA")
    for name, text in (("user-data", user_data), ("meta-data", metadata)):
        data = text.encode()
        iso.add_fp(
            io.BytesIO(data),
            len(data),
            iso_path="/" + name.upper().replace("-", "_") + ";1",
            rr_name=name,
            joliet_path="/" + name,
        )
    iso.write(str(output))
    iso.close()
    print("Created", output)


if __name__ == "__main__":
    main()
