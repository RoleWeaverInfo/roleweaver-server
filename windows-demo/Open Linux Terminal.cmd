@echo off
ssh -p 12222 -i "%~dp0runtime\admin-key" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="%~dp0runtime\known_hosts" roleweaver@127.0.0.1
pause
