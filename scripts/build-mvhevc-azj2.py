"""Package the source-only AZJ2 MV-HEVC runtime; libraries are generated on device."""
from pathlib import Path
from gxr_build import package

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'modules/mvhevc-eye-fix'
payload={p.relative_to(source).as_posix():p.read_bytes() for p in source.rglob('*') if p.is_file()}
payload['bin/source/build-mvhevc-azj2.py']=Path(__file__).read_bytes()
payload['bin/source/port-package.py']=(ROOT/'scripts/port-package.py').read_bytes()
payload['bin/source/gxr_build.py']=(ROOT/'scripts/gxr_build.py').read_bytes()
package(
    ROOT/'releases/gxr-mvhevc-eye-fix-azj2-0.1.0-disabled.zip',payload)
