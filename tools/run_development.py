"""Run the separate NWNX development server on UDP 5122."""

import json
import os
from pathlib import Path

base = Path(__file__).resolve().parent.parent
native = Path((base / "development/native_path.txt").read_text())
settings = json.loads((native / "server.json").read_text())
binary = native / "runtime/bin/linux-x86/nwserver-linux"
env = dict(os.environ)
env.update(
    LD_PRELOAD=str(native / "plugins/NWNX_Core.so"),
    LD_LIBRARY_PATH=str(native / "plugins"),
    NWNX_CORE_LOAD_PATH=str(native / "plugins"),
    NWNX_CORE_SKIP_ALL="1",
    NWNX_PLAYER_SKIP="n",
    NWNX_CREATURE_SKIP="n",
    NWNX_CHAT_SKIP="n",
    NWNX_EVENTS_SKIP="n",
    NWNX_REDIS_SKIP="n",
    NWNX_REDIS_HOST="127.0.0.1",
    NWNX_REDIS_PORT="6379",
    NWNX_CORE_LOG_LEVEL="6",
    NWNX_CORE_LOG_FILE_PATH=str(base / "development/nwnx.log"),
)
args = [
    str(binary),
    "-userdirectory",
    str(base / "development/userdata"),
    "-module",
    "RoleWeaver_Development",
    "-port",
    "5122",
    "-publicserver",
    "0",
    "-servername",
    "Role Weaver Development",
    "-servervault",
    "0",
    "-maxclients",
    "8",
    "-playerpassword",
    settings["player_password"],
    "-dmpassword",
    settings["dm_password"],
    "-interactive",
]
# A private FIFO keeps the interactive server console available without a visible terminal.
fifo = base / "development/console"
if not fifo.exists():
    os.mkfifo(fifo, 0o600)
fd = os.open(fifo, os.O_RDWR)
os.dup2(fd, 0)
os.close(fd)
os.chdir(binary.parent)
os.execve(binary, args, env)
