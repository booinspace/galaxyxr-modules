# Install from the KernelSU GXR catalogue

Open KernelSU GXR → Modules → the download button → the source dropdown, then
select **booinspace/galaxyxr-modules**. Existing managers can add
`https://github.com/booinspace/galaxyxr-modules` through **Sources → Add source**.
The custom manager build includes this source alongside 4uva4ek's repository.

Choose the modules you want and press **Install selected**. The manager checks
the download's SHA-256, module ID and version code before opening its normal
installer. GXR modules still install disabled; follow each module's activation
and recovery instructions. This catalogue is for **SM-I610 AZJ2** ports and
does not make upstream AZF3 builds compatible with AZJ2.

The catalogue lives in this repository, not inside a module ZIP or APK:

- [`modules.json`](../modules.json) lists the module IDs, names, descriptions,
  authors, experimental labels and update-feed URLs.
- [`updates/`](../updates/) contains each published version, integer version code,
  release ZIP URL, SHA-256 and documentation URL.
- The ZIPs remain in **GitHub Releases**. No binaries belong in the source tree.

The current releases are prereleases. An explicit catalogue lets the manager
offer them with its **Experimental** label; its release-only fallback otherwise
skips prereleases. Windows companions, the Steam Link builder, retired standalone
Rotation and unpublished builds are not listed.

## Update the catalogue

Upload the module ZIPs to a GitHub Release first. Generate the catalogue from
the published tags you want to offer:

```sh
python3 scripts/update-module-catalogue.py \
  --release azj2-modules-2026.11.14 \
  --release wifi-adb-v1.0.2-azj2
python3 -B tests/module-catalogue.test.py
git diff -- modules.json updates/
```

The generator verifies every selected archive against GitHub's asset digest,
checks the GXR installer layout and reads identity/version data from the actual
`module.prop`. For duplicate IDs it chooses the highest version code and rejects
different payloads with an identical version code. Existing working ZIPs are not
rebuilt or repackaged. Downloads are cached under ignored `.build/catalogue/`.

Publish the generated JSON files on the default branch, keeping these URLs
stable. A new published module version then needs a catalogue refresh, rather
than another manager APK rebuild. The standard `schemaVersion: 1` format is
implemented by [4uva4ek's source browser](https://github.com/4uva4ek/KernelSU-GXR/tree/ec924a8add6a89efda6a3c2e837e5812e0377ee8).
Catalogue generation and AZJ2 distribution are by **booinspace**; original
module creators remain credited in the README, catalogue metadata and ZIPs.

## Update lookup

Browsing and installation use the selected source. Installed modules keep
their own `updateJson` when one is present. For older modules without that field,
the manager consults configured catalogues and refuses to pick between different
feeds claiming the same module ID. Several AZJ2 ports share upstream IDs, so use
the **booinspace** source to select the AZJ2 package rather than relying on an
ambiguous automatic-update fallback. This behaviour is retained from upstream.
