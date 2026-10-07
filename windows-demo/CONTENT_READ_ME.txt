EDITABLE WORLD FILES

These Windows folders are convenient staging folders. They are not shared live
with Linux and do not replace your running world automatically.

Advanced access uses the optional Windows OpenSSH client (or an SFTP client).
The standard SSH port is 12222, username roleweaver, and the private key is
userdata/admin-key. In PowerShell, open a terminal in the extracted demo folder:

ssh -p 12222 -i .\userdata\admin-key -o IdentitiesOnly=yes -o UserKnownHostsFile=.\userdata\known_hosts roleweaver@127.0.0.1

Accept the SSH host key on the first connection to your own local demo. The
known_hosts file then lets SSH detect changes. Use your selected SSH port if you
changed it in Advanced settings. Your private key grants local Linux admin access.

Stop only the game/addon service while leaving the VM and SSH running:

sudo systemctl stop roleweaver-demo

Linux paths:
  Editable source: /home/roleweaver/demo
  World settings:  /home/roleweaver/demo/.demo/qemu_demo/settings.json
  Game files:      /home/roleweaver/demo/.demo/qemu_demo/userdata/
  Module folder:   game files/modules/
  HAK folder:      game files/hak/
  TLK folder:      game files/tlk/
  Native tools:   /home/roleweaver/native/

Use SFTP or scp to copy your module/HAKs/TLK to the corresponding game folders.
For example, run this in Windows PowerShell (use your actual module filename):

scp -P 12222 -i .\userdata\admin-key -o IdentitiesOnly=yes -o UserKnownHostsFile=.\userdata\known_hosts .\content\hak\example.hak roleweaver@127.0.0.1:/home/roleweaver/demo/.demo/qemu_demo/userdata/hak/

For small layout edits, download userdata/modules/YourWorld_Fixed.mod, edit a copy
in Aurora on Windows, and upload it under the SAME name while the service is
stopped. Keep its existing Role Weaver scripts, hooks and demo resource names.
Then in the SSH terminal run:

sudo systemctl start roleweaver-demo

For a completely different module, follow the existing-server integration guide
inside /home/roleweaver/demo/addon. The roleweaver scripts/hooks must be installed
and its content must match the selected world. Simply renaming an arbitrary .mod
does not add AI functionality. The demo runner loads YourWorld_Fixed by name.
Its compile/rebuild command uses the source module/content paths in settings.json
and writes the prepared module under that runtime name. Read demo/CUSTOMIZE.md
before changing the source module, content paths or rebuilding the demo.

Changing module requires restarting the game service, disconnecting players.
It does not require rebuilding the Linux VM or installing another VM manager.
