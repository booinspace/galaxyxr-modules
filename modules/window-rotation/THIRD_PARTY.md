# Sources and credits

- [BlueScorpioVR/galaxyxr-modules](https://github.com/BlueScorpioVR/galaxyxr-modules)
  supplies the combined package's curvature engine and informed the
  supervised injection and caption-menu integration.
- The local Java rotation helper uses the stock AZJ2 CPM quaternion API and
  shares the Curvature menu owner and supervisor.
- [Frida 17.23.3](https://github.com/frida/frida/releases/tag/17.23.3) supplies
  the unmodified Android arm64 injector, with ELF SHA-256
  `bc4e1a0c7ede20af387e9e002a535cb3ff0072f523c460692820473b3f07e122`.
  Packages include upstream COPYING and LGPL 2.0-or-later notices.
- [frida-java-bridge 7.0.13](https://www.npmjs.com/package/frida-java-bridge/v/7.0.13)
  is bundled in the shared agent from the hash-pinned npm archive.
- [ECJ 3.39.0](https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.39.0/)
  and [Android D8/R8](https://developer.android.com/tools/d8) are host build
  tools, not software installed on the headset.

The [project credits](../../docs/SOURCES.md) record upstream pins and terms.
The firmware binaries used for compatibility inspection are not distributed.
