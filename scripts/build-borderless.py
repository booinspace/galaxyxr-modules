"""Build the disabled AZJ2-only KernelSU borderless-window module."""

import argparse
import base64
import hashlib
import io
import lzma
from pathlib import Path
import tarfile
import tempfile
import urllib.request

from gxr_build import package, validate_arm64

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "modules/borderless-windows"
INJECT_SHA256 = "fa27b0478fbe1909978388d606236008c40e19ffddcea3bca69a6ed54fde02dc"
BINARY_SHA256 = "bc4e1a0c7ede20af387e9e002a535cb3ff0072f523c460692820473b3f07e122"
BRIDGE_SHA512 = "YSyKjxbxKnSi3KSUy9vciOvTOuq0RRh9dkxzkQVEdfIIZlw20zE8D3Cq9eL2FDqUVj4YKas6Wf09kCjL5zbffg=="


def fetch(cache: Path, name: str, url: str) -> bytes:
    path = cache / name
    if not path.exists():
        with urllib.request.urlopen(url, timeout=120) as response:
            path.write_bytes(response.read())
    return path.read_bytes()


def build(cache: Path, output: Path) -> Path:
    import frida

    if frida.__version__ != "17.23.3":
        raise ValueError("Build with frida==17.23.3")
    cache.mkdir(parents=True, exist_ok=True)
    archive = fetch(
        cache,
        "frida-inject-17.23.3-android-arm64.xz",
        "https://github.com/frida/frida/releases/download/17.23.3/frida-inject-17.23.3-android-arm64.xz",
    )
    if hashlib.sha256(archive).hexdigest() != INJECT_SHA256:
        raise ValueError("Frida archive hash mismatch")
    injector = lzma.decompress(archive)
    if hashlib.sha256(injector).hexdigest() != BINARY_SHA256:
        raise ValueError("Frida binary hash mismatch")
    validate_arm64(injector)
    bridge = fetch(
        cache,
        "frida-java-bridge-7.0.13.tgz",
        "https://registry.npmjs.org/frida-java-bridge/-/frida-java-bridge-7.0.13.tgz",
    )
    if base64.b64encode(hashlib.sha512(bridge).digest()).decode() != BRIDGE_SHA512:
        raise ValueError("Java bridge hash mismatch")

    source_names = (
        "module.prop", "disable", "skip_mount", "service.sh", "action.sh", "auto.sh",
        "control.sh", "uninstall.sh", "firmware.sha256", "install-info.txt",
        "README.md", "THIRD_PARTY.md",
    )
    payload = {name: (MODULE / name).read_bytes() for name in source_names}
    if payload["disable"] or payload["skip_mount"]:
        raise ValueError("The install markers must be empty")
    payload["bin/frida-inject"] = injector
    payload["bin/third-party/frida-java-bridge-7.0.13.tgz"] = bridge
    payload["bin/licenses/frida-COPYING"] = fetch(
        cache, "frida-17.23.3-COPYING", "https://raw.githubusercontent.com/frida/frida-core/17.23.3/COPYING"
    )
    payload["bin/licenses/LGPL-2.0-or-later.txt"] = fetch(
        cache, "LGPL-2.0-or-later.txt",
        "https://raw.githubusercontent.com/spdx/license-list-data/v3.27.0/text/LGPL-2.0-or-later.txt",
    )
    payload["bin/source/agent.js"] = (MODULE / "agent.js").read_bytes()
    payload["bin/source/build-borderless.py"] = Path(__file__).read_bytes()

    payload["bin/source/gxr_build.py"] = (ROOT / "scripts/gxr_build.py").read_bytes()

    with tempfile.TemporaryDirectory(prefix="gxr-borderless-") as temporary:
        project = Path(temporary)
        (project / "agent.js").write_bytes(payload["bin/source/agent.js"])
        bridge_dir = project / "node_modules/frida-java-bridge"
        bridge_dir.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(bridge), mode="r:gz") as members:
            for member in members.getmembers():
                if not member.isfile():
                    continue
                relative = Path(member.name).relative_to("package")
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("Unsafe Java bridge archive member")
                destination = bridge_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(members.extractfile(member).read())
        diagnostics = []
        compiler = frida.Compiler()
        compiler.on("diagnostics", diagnostics.append)
        bundle = compiler.build("agent.js", project_root=str(project))
        if diagnostics:
            raise ValueError(f"Frida compiler diagnostics: {diagnostics}")
        payload["bin/agent.js"] = bundle.encode()

    result = output / "gxr-borderless-azj2-0.2.0-disabled.zip"
    return package(result, payload, executables=("bin/frida-inject",), timestamp=(2026, 11, 11, 0, 0, 0))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "releases")
    args = parser.parse_args()
    build(args.cache, args.output)
