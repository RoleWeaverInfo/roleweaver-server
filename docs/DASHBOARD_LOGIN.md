# Dashboard password

Open the usual dashboard address and sign in with **roleweaver** on a new
installation. The demo uses the same initial dashboard password. This is separate
from the NWN player/DM passwords and your LLM API keys.

Use **Log out** in the top bar when finished. A login lasts up to 12 hours and is
invalidated by a Role Weaver service restart or a server-side password change.
Passwords are not saved in browser storage. Your browser may offer its own password
manager. Unsaved draft recovery continues to use this browser's local storage;
logging out does not erase those drafts, so use a private browser profile on a
shared computer.

## Change or reset the password on Ubuntu

For an installed world named `my_world`, run:

```bash
cd "$HOME/.local/share/roleweaver/my_world/current"
python3 -m roleweaver.dashboard_auth --config "$HOME/.local/share/roleweaver/my_world/config.json"
```

Enter the new password twice when prompted. Typing is hidden. Use 8–256 characters.
The change takes effect without restarting either service; other dashboard logins
are revoked. You do not need the old password when running this as the server owner.
Replace `my_world` with your installed world ID if different.

For the demo, run this **from the extracted package folder**:

```bash
python3 -m roleweaver.dashboard_auth --config .demo/rw_demo/config.json
```

If you chose a different demo instance name, replace `rw_demo`. Keep the password
out of shell command arguments, Git and bug reports. Do not put it in NPC profiles,
lore or the LLM configuration.

## Storage and access

`dashboard-auth.json` is created beside the runtime `config.json` on the first
dashboard start. It contains a salted password hash and a separate credential for
read-only server checks. On Linux it is created with owner-only permissions. The
file stays outside managed application releases and world databases: updates and
world restores retain it. Packages, Git, support reports and world backups exclude
it. If it becomes damaged, use the reset command above; login fails closed until
it is repaired. Do not delete it to change a password.

Every dashboard page and data API, including health, downloads and database
recovery, requires authentication. Only the login page, its artwork and script are
public. The installer reads the local check credential so verification and updates
continue to work without password prompts. That credential can read only the
specific readiness endpoints; it cannot change settings or download backups.

For the older standalone readiness checker, supply the installed configuration:

```bash
python3 tools/check_addon.py --port 8743 --config "$HOME/.local/share/roleweaver/my_world/config.json"
```

Login checks are limited to ten attempts per minute and one password verification
at a time. Wait a minute if attempts are refused. A maximum of 32 browser sessions
are retained; starting another drops the oldest session.

This is one shared administrator password, not separate DM/player accounts. Anyone
who knows it can administer the world. Change the published default before sharing
access. Keep the dashboard on localhost and use the existing SSH tunnel; this
does not add public HTTPS hosting. See [security boundaries](SECURITY_AND_LIMITS.md).

Implementation: PBKDF2-HMAC-SHA256 with 600,000 iterations and a random salt,
constant-time password-hash comparison, random session cookies with HttpOnly and
SameSite=Strict, and existing Host/Origin checks. Password hashing and cookie
handling follow the relevant [OWASP password-storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
and [session-management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
guidance. Cookies are restricted to this local HTTP setup; the Secure flag is not
used because the dashboard is served over loopback HTTP inside the SSH tunnel.
