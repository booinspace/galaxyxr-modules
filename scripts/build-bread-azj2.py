"""Build the three disabled AZJ2 ports of BreadDoesStuff's MIT-licensed modules."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile

from gxr_build import class_archive, dex, package, resolve_tools, sha256 as sha

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "93dcf733068d0f57d53b21b79f37b1f38f573e6f"
MODULES = ("mic-gain-boost", "passthrough-anywhere", "no-lowlight-toast")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("java", "javac", "r8", "android-jar"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "releases")
    parser.add_argument("--module", choices=MODULES, help="Build only the requested port")
    args = parser.parse_args()
    resolve_tools(parser, args, ("java", "javac", "r8", "android_jar"))
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

        for name in ([args.module] if args.module else MODULES):
            module = ROOT / "modules" / name
            payload = {path.name: path.read_bytes() for path in module.iterdir() if path.is_file()}
            for path in sorted((module / "webroot").rglob("*")):
                # User recordings are runtime data, never release inputs.
                if path.is_file() and "recordings" not in path.relative_to(module / "webroot").parts:
                    payload[path.relative_to(module).as_posix()] = path.read_bytes()
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
            payload["bin/source/gxr_build.py"] = (ROOT / "scripts/gxr_build.py").read_bytes()
            receipt = {"upstream": "BreadDoesStuff/galaxy-xr-modules", "commit": UPSTREAM,
                       "target": "SM-I610 I610UES3AZJ2", "status": "experimental; device behavior untested",
                       "tools": {key: sha(getattr(args, key).read_bytes()) for key in ("java", "javac", "r8", "android_jar")},
                       "source": {path: sha(data) for path, data in payload.items() if path.startswith("bin/source/")}}
            payload["bin/build-info.json"] = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
            version = next(line.split("=", 1)[1].split("-", 1)[0]
                           for line in payload["module.prop"].decode().splitlines() if line.startswith("version="))
            output = args.output / f"gxr-{name}-azj2-{version}-disabled.zip"
            package(output, payload, timestamp=(2026, 11, 11, 0, 0, 0))


if __name__ == "__main__": main()
