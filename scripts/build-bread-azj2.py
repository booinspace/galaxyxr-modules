"""Build the three disabled AZJ2 ports of BreadDoesStuff's MIT-licensed modules."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "93dcf733068d0f57d53b21b79f37b1f38f573e6f"
MODULES = ("mic-gain-boost", "passthrough-anywhere", "no-lowlight-toast")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def class_archive(directory, target):
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for source in sorted(directory.rglob("*.class")):
            archive.write(source, source.relative_to(directory).as_posix())


def dex(args, jar, stubs, destination):
    destination.mkdir()
    command = [str(args.java), "-cp", str(args.r8), "com.android.tools.r8.D8", "--release", "--min-api", "34",
               "--lib", str(args.android_jar), "--output", str(destination)]
    if stubs is not None:
        command += ["--classpath", str(stubs)]
    subprocess.run(command + [str(jar)], check=True)
    result = (destination / "classes.dex").read_bytes()
    if not result.startswith(b"dex\n") or len(list(destination.glob("*.dex"))) != 1:
        raise ValueError("Expected one helper DEX")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("java", "javac", "r8", "android-jar"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "releases")
    args = parser.parse_args()
    for name in ("java", "javac", "r8", "android_jar"):
        value = getattr(args, name).resolve()
        if not value.is_file(): parser.error(f"Missing tool: {name}")
        setattr(args, name, value)
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gxr-bread-build-") as temporary:
        work = Path(temporary)
        tests = work / "tests"
        tests.mkdir()
        subprocess.run([str(args.javac), "--release", "8", "-d", str(tests),
                        str(ROOT / "modules/mic-gain-boost/src/com/gxr/mic/GainState.java"),
                        str(ROOT / "modules/passthrough-anywhere/src/com/gxr/pt/PassthroughPolicy.java"),
                        str(ROOT / "tests/PortPolicyTest.java"), str(ROOT / "tests/PortApiProbe.java")], check=True)
        subprocess.run([str(args.java), "-cp", str(tests), "PortPolicyTest"], check=True)
        probe_jar = work / "probe.jar"
        with ZipFile(probe_jar, "w") as archive: archive.write(tests / "PortApiProbe.class", "PortApiProbe.class")
        probe = dex(args, probe_jar, None, work / "probe-dex")
        (args.output / "bread-azj2-api-probe.dex").write_bytes(probe)

        for name in MODULES:
            module = ROOT / "modules" / name
            payload = {path.name: path.read_bytes() for path in module.iterdir() if path.is_file()}
            helper_sources = sorted((module / "src").rglob("*.java"))
            stubs_sources = sorted((module / "stubs").rglob("*.java"))
            for source in helper_sources + stubs_sources:
                payload["bin/source/" + source.relative_to(module).as_posix()] = source.read_bytes()
            if helper_sources:
                payload["bin/runtime.sh"] = (ROOT / "scripts/bread-port/daemon-control.sh").read_bytes()
                target = work / name
                classes = target / "classes"
                stubs = target / "stubs"
                classes.mkdir(parents=True); stubs.mkdir()
                subprocess.run([str(args.javac), "--release", "8", "-nowarn", "-classpath", str(args.android_jar),
                                "-d", str(stubs), *(str(path) for path in stubs_sources)], check=True)
                runtime = ROOT / "scripts/bread-port/PortRuntime.java"
                subprocess.run([str(args.javac), "--release", "8", "-nowarn", "-classpath", f"{stubs}:{args.android_jar}",
                                "-d", str(classes), str(runtime), *(str(path) for path in helper_sources)], check=True)
                payload["bin/source/PortRuntime.java"] = runtime.read_bytes()
                jar = target / "helper.jar"
                class_archive(classes, jar)
                with ZipFile(jar) as archive:
                    if any(path.startswith("android/") for path in archive.namelist()):
                        raise ValueError("Compile-only Android stubs must not be packaged")
                payload["bin/helper.dex"] = dex(args, jar, stubs, target / "dex")
            if payload["disable"] or payload["skip_mount"]:
                raise ValueError("Release must install disabled with skip_mount")
            payload["bin/source/build-bread-azj2.py"] = Path(__file__).read_bytes()
            receipt = {"upstream": "BreadDoesStuff/galaxy-xr-modules", "commit": UPSTREAM,
                       "target": "SM-I610 I610UES3AZJ2", "status": "experimental; device behavior untested",
                       "tools": {key: sha(getattr(args, key).read_bytes()) for key in ("java", "javac", "r8", "android_jar")},
                       "source": {path: sha(data) for path, data in payload.items() if path.startswith("bin/source/")}}
            payload["bin/build-info.json"] = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
            payload["SHA256SUMS"] = "".join(f"{sha(data)}  {path}\n" for path, data in sorted(payload.items())
                                            if path != "disable").encode()
            output = args.output / f"gxr-{name}-azj2-0.1.1-disabled.zip"
            with ZipFile(output, "w", ZIP_DEFLATED) as archive:
                for path, data in sorted(payload.items()):
                    entry = ZipInfo(path, (2026, 11, 11, 0, 0, 0))
                    entry.create_system = 3; entry.compress_type = ZIP_DEFLATED
                    entry.external_attr = (0o100755 if path.endswith(".sh") else 0o100644) << 16
                    archive.writestr(entry, data)
            with ZipFile(output) as archive:
                if archive.testzip() is not None or set(archive.namelist()) != set(payload):
                    raise ValueError("Package integrity check failed")
                for path, data in payload.items():
                    if archive.read(path) != data: raise ValueError("Package mismatch: " + path)
                for forbidden in ("system.prop", "post-fs-data.sh", "post-mount.sh", "sepolicy.rule"):
                    if forbidden in archive.namelist(): raise ValueError("Unsupported GXR startup payload")
            output.with_suffix(".zip.sha256").write_text(f"{sha(output.read_bytes())}  {output.name}\n")
            print(output)


if __name__ == "__main__": main()
