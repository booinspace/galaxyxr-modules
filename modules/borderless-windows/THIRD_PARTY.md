# Runtime components and credits

- **Frida 17.23.3**: unmodified `frida-inject` Android arm64 binary, downloaded
  from the [official release](https://github.com/frida/frida/releases/tag/17.23.3).
  The release ZIP includes its upstream `COPYING` notice and the LGPL 2.0 or
  later text. Injector archive SHA-256:
  `fa27b0478fbe1909978388d606236008c40e19ffddcea3bca69a6ed54fde02dc`.
  Decompressed ELF SHA-256:
  `bc4e1a0c7ede20af387e9e002a535cb3ff0072f523c460692820473b3f07e122`.
- **frida-java-bridge 7.0.13**: bundled into the agent from the
  [official package](https://www.npmjs.com/package/frida-java-bridge/v/7.0.13).
  The original npm archive is also included in the release ZIP. SHA-512 in
  base64:
  `YSyKjxbxKnSi3KSUy9vciOvTOuq0RRh9dkxzkQVEdfIIZlw20zE8D3Cq9eL2FDqUVj4YKas6Wf09kCjL5zbffg==`.
- **BlueScorpioVR/galaxyxr-modules**: reference for the disabled GXR module
  format, injector lifecycle and firmware hash guard. Its curvature agent is
  not copied into this module.

The Python `frida` package is a build tool, not installed on the headset.
