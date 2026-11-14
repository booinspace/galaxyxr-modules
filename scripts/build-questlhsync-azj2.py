"""Build the pinned MIT QuestLHSync Galaxy XR source with Android NDK 28.2."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

from gxr_build import ndk_compiler, package, validate_arm64

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'modules/questlhsync'
UPSTREAM=MODULE/'upstream'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk',required=True,type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'releases')
    args=parser.parse_args()
    compiler=ndk_compiler(args.ndk,'28.2.13676358',29)
    with tempfile.TemporaryDirectory(prefix='gxr-lighthouse-build-') as temporary:
        work=Path(temporary)
        common=[str(compiler),'-O2','-Wall','-Wextra','-Werror','-Wl,-z,max-page-size=16384']
        builds={
            'lhsyncd':['-Wno-unused-but-set-variable','-DMODULE_VERSION="gxr-azj2-0.1.1"',
                       '-DHS_TIMER_CLOCK=CLOCK_BOOTTIME','-DHS_LOG_CAPTURE_STATUS=1',
                       '-I'+str(UPSTREAM/'vendor/questlhsync'),
                       str(UPSTREAM/'vendor/questlhsync/lhsyncd.c'),str(UPSTREAM/'src/gxr.c')],
            'gxr-prepare':['-ffp-contract=off',str(UPSTREAM/'src/prepare.c'),'-lm'],
        }
        for source,binary in [('capture.c','gxr-lhsight'),('head_origin.c','gxr-head-origin')]:
            builds[binary]=['-nostdlib','-fPIE','-pie','-fno-stack-protector',
                            '-Wl,-e,_start','-Wl,--dynamic-linker=/system/bin/linker64',
                            str(UPSTREAM/'src/start.S'),str(UPSTREAM/'src'/source),'-lc','-ldl']
        for binary,flags in builds.items():
            subprocess.run([*common,*flags,'-o',str(work/binary)],check=True)
        payload={p.relative_to(MODULE).as_posix():p.read_bytes() for p in MODULE.rglob('*')
                 if p.is_file() and 'upstream' not in p.relative_to(MODULE).parts}
        for binary in builds:
            blob=(work/binary).read_bytes()
            validate_arm64(blob)
            payload['bin/'+binary]=blob
        source=io.BytesIO()
        with tarfile.open(fileobj=source,mode='w') as archive:
            for p in sorted(UPSTREAM.rglob('*')):
                if not p.is_file(): continue
                info=tarfile.TarInfo(p.relative_to(UPSTREAM).as_posix()); data=p.read_bytes()
                info.size=len(data); info.mode=0o644; archive.addfile(info,io.BytesIO(data))
        payload['bin/source/upstream.tar.gz']=gzip.compress(source.getvalue(),mtime=0)
        payload['bin/source/build-questlhsync-azj2.py']=Path(__file__).read_bytes()
        payload['bin/source/port-package.py']=(ROOT/'scripts/port-package.py').read_bytes()
        payload['bin/source/gxr_build.py']=(ROOT/'scripts/gxr_build.py').read_bytes()
        payload['LICENSE.upstream']=(UPSTREAM/'LICENSE').read_bytes()
        receipt={'upstream':json.loads((MODULE/'UPSTREAM.json').read_text()),
                 'ndk':'28.2.13676358','runtime':'Android bionic; separate QVR child retained',
                 'status':'AZJ2 library identities verified; live capture/alignment not yet tested',
                 'source':{str(p.relative_to(UPSTREAM)):hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(UPSTREAM.rglob('*')) if p.is_file()}}
        payload['bin/build-info.json']=(json.dumps(receipt,indent=2,sort_keys=True)+'\n').encode()
        package(args.output/'gxr-questlhsync-azj2-0.1.1-disabled.zip',payload,
               executables=['bin/'+binary for binary in builds])


if __name__=='__main__': main()
