ROLE WEAVER REMOTE INSTALLER 1.0

This Windows application uploads a Role Weaver Server Add-on release to an
existing Linux NWN:EE/NWNX server, opens an SSH tunnel and launches the guided
Linux setup page. It does not install NWN or NWNX.

Requirements
------------
- Windows 10 or 11 with the optional OpenSSH Client installed.
- SSH access to the Linux account that owns the NWN server.
- A downloaded RoleWeaver-Server-Addon-*.tar.gz release.
- Python 3 on Linux. The guided setup reports other missing prerequisites.

Use
---
1. Run "Role Weaver Remote Installer.exe".
2. Enter the Linux host, SSH port and username.
3. Optionally select an SSH private key. Enter a password or key passphrase only
   when required.
4. Select Test SSH login. Continue after the log reports that login succeeded.
5. Select the Server Add-on .tar.gz archive.
6. Select Connect and open setup.
7. Complete the guided setup in the browser. Keep the Windows application open.
8. Close the connection when finished.

The archive is streamed through the authenticated SSH connection and extracted
under ~/.cache/roleweaver-remote-installer for the lifetime of the connection.
The temporary extraction is removed when setup closes. The installed Role Weaver
service and its saved configuration remain on Linux.

Security
--------
Passwords and key passphrases stay in process memory and are never saved by the
installer. OpenSSH's known_hosts file is used normally: new host keys may be
accepted once and changed keys are rejected. The setup and dashboard remain bound
to Linux loopback and are reached through SSH. Never expose their ports publicly.

If Windows OpenSSH is missing, open Settings > Optional Features and install
OpenSSH Client. For advanced/manual setup, extract the Linux package on the server
and run: bash setup.sh gui

Troubleshooting
---------------
Connection and validation messages appear in the lower panel. The same messages
are saved to:

%LOCALAPPDATA%\RoleWeaver\RemoteInstaller\installer.log

The log does not contain the entered password or key passphrase. Use Test SSH
login first to distinguish an SSH authentication problem from an archive upload,
local port or guided-setup problem.
