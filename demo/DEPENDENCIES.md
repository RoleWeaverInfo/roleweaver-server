# Demo dependencies

The archive contains Role Weaver source, an editable demo module, authored content and scripts.
It does not redistribute the NWN installation or NWNX/compiler binaries.

1. Obtain the Linux dedicated server from [Beamdog's server downloads](https://nwn.beamdog.net/downloads/).
2. Choose the NWNX release that matches that server build using the
   [official NWNX compatibility instructions](https://github.com/nwnxee/unified/blob/master/README.md).
   Obtain plugins and the matching NWScript headers from the same release. Do not mix releases.
3. Obtain/build a Linux `nwnsc` compiler. Existing NWN server developers can reuse their installed
   compiler. Ensure it is executable (`chmod +x /your/path/nwnsc`). This demo does not install compilers.
4. Arrange the dependencies as below, or make symlinks to existing directories. You can choose any
   root location and pass it through `--native`; nothing requires the author's VM paths.

```text
nwn-demo-deps/
  runtime/
    bin/linux-x86/nwserver-linux
    data/                         NWN key/bif resources from the runtime
  plugins/
    NWNX_Core.so
    NWNX_Chat.so
    NWNX_Events.so
    NWNX_Redis.so
    NWNX_Creature.so
    NWNX_Player.so
  nwscripts/                      matching NWNX .nss headers
    nwnx_chat.nss
    ...
```

Keep Redis on localhost (default 6379). The demo enables only the plugins it uses. A matching server
and plugin build is necessary; file presence checks alone cannot prove binary compatibility.

The first setup links the selected compiler at `tools/nwnsc`. A different existing compiler link is
not silently replaced. Native runtime/game files remain in their supplied location and are never
modified by the demo builder. The demo writes only inside its own instance directory.

Known scope: Linux x86-64 with the NWN executable at `runtime/bin/linux-x86/nwserver-linux`.
An ARM host or a differently packaged runtime needs separate compatibility work. A VM is acceptable;
the NWN client may run on the host computer. Allow adequate CPU/RAM for a locally hosted LLM.
