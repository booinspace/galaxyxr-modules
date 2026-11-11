"""Build the disabled AZJ2 rotation module and run its host math checks."""

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "modules/window-rotation"
RUNTIME = ROOT / "releases/gxr-borderless-azj2-0.2.0-disabled.zip"
RUNTIME_SHA256 = "fdc64436744280570c40c0016692d0f7b2876f300782185093a0fa4b9b2a28a4"
ECJ_SHA256 = "01f5a92ac19bb2b3bf85e295a68f2c73c264369109158b566ce9b490af982948"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(args) -> Path:
    import frida

    if frida.__version__ != "17.23.3":
        raise ValueError("Use frida==17.23.3")
    if digest(args.ecj.read_bytes()) != ECJ_SHA256:
        raise ValueError("Use the verified ECJ 3.39.0 compiler")
    if digest(RUNTIME.read_bytes()) != RUNTIME_SHA256:
        raise ValueError("Pinned runtime ZIP checksum mismatch")
    with ZipFile(RUNTIME) as runtime:
        payload = {name: runtime.read(name) for name in (
            "bin/frida-inject", "bin/third-party/frida-java-bridge-7.0.13.tgz",
            "bin/licenses/frida-COPYING", "bin/licenses/LGPL-2.0-or-later.txt",
        )}
    for name in ("module.prop", "action.sh", "service.sh", "auto.sh", "control.sh",
                 "uninstall.sh", "firmware.sha256", "install-info.txt", "README.md", "THIRD_PARTY.md",
                 "disable", "skip_mount"):
        payload[name] = (MODULE / name).read_bytes()
    if payload["disable"] or payload["skip_mount"]:
        raise ValueError("Install markers must be empty")
    sources = sorted((MODULE / "android").rglob("*.java"))
    test = ROOT / "tests/RotationMathTest.java"
    for source in sources:
        payload["bin/source/" + source.relative_to(MODULE).as_posix()] = source.read_bytes()
    payload["bin/source/RotationMathTest.java"] = test.read_bytes()
    payload["bin/source/agent.js"] = (MODULE / "agent.js").read_bytes()
    payload["bin/source/build-window-rotation.py"] = Path(__file__).read_bytes()

    with tempfile.TemporaryDirectory(prefix="gxr-rotation-") as temporary:
        work = Path(temporary)
        classes = work / "classes"
        classes.mkdir()
        subprocess.run([str(args.java), "-jar", str(args.ecj), "-source", "1.8", "-target", "1.8",
                        "-proc:none", "-failOnWarning", "-classpath", str(args.android_jar),
                        "-d", str(classes), *(str(path) for path in sources), str(test)], check=True)
        subprocess.run([str(args.java), "-cp", str(classes), "local.gxr.rotation.RotationMathTest"], check=True)
        helper = work / "helper.jar"
        with ZipFile(helper, "w", ZIP_DEFLATED) as archive:
            for path in sorted(classes.rglob("*.class")):
                if not path.name.startswith("RotationMathTest"):
                    archive.write(path, path.relative_to(classes).as_posix())
        dex_output = work / "dex"
        dex_output.mkdir()
        subprocess.run([str(args.java), "-cp", str(args.r8), "com.android.tools.r8.D8",
                        "--min-api", "26", "--lib", str(args.android_jar),
                        "--output", str(dex_output), str(helper)], check=True)
        dex = (dex_output / "classes.dex").read_bytes()
        if not dex.startswith(b"dex\n") or len(list(dex_output.glob("*.dex"))) != 1:
            raise ValueError("Expected one helper DEX")
        payload["bin/classes.dex"] = dex
        source = payload["bin/source/agent.js"].decode()
        if source.count("__ROTATION_DEX_BASE64__") != 1:
            raise ValueError("Missing or repeated DEX placeholder")
        (work / "agent.js").write_text(source.replace("__ROTATION_DEX_BASE64__", base64.b64encode(dex).decode()))
        bridge = work / "node_modules/frida-java-bridge"
        bridge.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(payload["bin/third-party/frida-java-bridge-7.0.13.tgz"]), mode="r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                relative = Path(member.name).relative_to("package")
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("Unsafe Java bridge archive path")
                destination = bridge / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.extractfile(member).read())
        diagnostics = []
        compiler = frida.Compiler()
        compiler.on("diagnostics", diagnostics.append)
        payload["bin/agent.js"] = compiler.build("agent.js", project_root=str(work)).encode()
        if diagnostics:
            raise ValueError(f"Frida compiler diagnostics: {diagnostics}")

    payload["bin/build-info.json"] = (json.dumps({
        "target": "SM-I610 I610UES3AZJ2", "status": "experimental; disabled on installation",
        "runtimeZipSha256": RUNTIME_SHA256, "helperDexSha256": digest(dex),
        "dependencies": {name: digest(getattr(args, name).read_bytes())
                         for name in ("java", "ecj", "r8", "android_jar")},
        "sourceSha256": {name: digest(data) for name, data in sorted(payload.items())
                         if name.startswith("bin/source/")},
    }, indent=2, sort_keys=True) + "\n").encode()
    payload["SHA256SUMS"] = "".join(
        f"{digest(data)}  {name}\n" for name, data in sorted(payload.items()) if name != "disable"
    ).encode()
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output / "gxr-window-rotation-azj2-0.1.2-disabled.zip"
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            entry = ZipInfo(name, (2026, 11, 11, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = (0o100755 if name.endswith(".sh") or name == "bin/frida-inject" else 0o100644) << 16
            archive.writestr(entry, data)
    with ZipFile(output) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(payload):
            raise ValueError("Package integrity check failed")
        for name, data in payload.items():
            if archive.read(name) != data:
                raise ValueError(f"Package payload mismatch: {name}")
    output.with_suffix(".zip.sha256").write_text(f"{digest(output.read_bytes())}  {output.name}\n")
    print(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("java", "ecj", "r8", "android-jar"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "releases")
    args = parser.parse_args()
    for name in ("java", "ecj", "r8", "android_jar"):
        path = getattr(args, name).resolve()
        if not path.is_file():
            parser.error(f"Missing build tool: {name}")
        setattr(args, name, path)
    build(args)
