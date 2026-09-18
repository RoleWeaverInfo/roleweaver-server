import os, json
from pathlib import Path

b = Path(__file__).resolve().parents[1] / "test-runtime"
n = Path.home() / "Documents/RoleWeaver-Native-Server"
s = json.loads((n / "server.json").read_text())
e = dict(os.environ)
e.update(
    LD_PRELOAD=str(n / "plugins/NWNX_Core.so"),
    LD_LIBRARY_PATH=str(n / "plugins"),
    NWNX_CORE_LOAD_PATH=str(n / "plugins"),
    NWNX_CORE_SKIP_ALL="1",
    NWNX_PLAYER_SKIP="n",
    NWNX_CREATURE_SKIP="n",
    NWNX_CHAT_SKIP="n",
    NWNX_EVENTS_SKIP="n",
    NWNX_REDIS_SKIP="n",
    NWNX_REDIS_HOST="127.0.0.1",
    NWNX_REDIS_PORT="6379",
    NWNX_CORE_LOG_LEVEL="6",
    NWNX_CORE_LOG_FILE_PATH=str(b / "nwnx.log"),
)
f = b / "console"
if not f.exists():
    os.mkfifo(f, 0o600)
fd = os.open(f, os.O_RDWR)
os.dup2(fd, 0)
os.close(fd)
binary = n / "runtime/bin/linux-x86/nwserver-linux"
a = [
    str(binary),
    "-userdirectory",
    str(b / "userdata"),
    "-module",
    "YourWorld",
    "-port",
    "5124",
    "-publicserver",
    "0",
    "-servername",
    "Role Weaver YourWorld Package Test",
    "-servervault",
    "0",
    "-maxclients",
    "8",
    "-reloadwhenempty",
    "0",
    "-playerpassword",
    s["player_password"],
    "-dmpassword",
    s["dm_password"],
    "-interactive",
]
os.chdir(binary.parent)
os.execve(binary, a, e)
