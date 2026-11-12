"""Package a disabled curvature recovery module for KernelSU GXR."""

import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "modules/curvature-recovery"
OUTPUT = ROOT / "releases/gxr-curvature-recovery-0.1.5-disabled.zip"


def main() -> None:
    payload = {name: (SOURCE / name).read_bytes() for name in (
        "module.prop", "action.sh", "service.sh", "auto.sh", "disable", "skip_mount"
    )}
    if payload["disable"] or payload["skip_mount"]:
        raise ValueError("Install markers must be empty")
    payload["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in sorted(payload.items()) if name != "disable"
    ).encode()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            entry = ZipInfo(name, (2026, 11, 11, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            archive.writestr(entry, data)
    with ZipFile(OUTPUT) as archive:
        for name, data in payload.items():
            if archive.read(name) != data:
                raise ValueError(f"Package verification failed: {name}")
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    OUTPUT.with_suffix(".zip.sha256").write_text(f"{digest}  {OUTPUT.name}\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
