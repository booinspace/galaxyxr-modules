"""Build the pinned MIT QuestLHSync Galaxy XR source with Android NDK 28.2."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
import runpy
import subprocess
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'modules/questlhsync'
UPSTREAM=MODULE/'upstream'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk',required=True,type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'releases')
    args=parser.parse_args()
    ndk=args.ndk.resolve()
    if 'Pkg.Revision = 28.2.13676358' not in (ndk/'source.properties').read_text():
        parser.error('Android NDK 28.2.13676358 required')
    host={'Linux':'linux-x86_64','Darwin':'darwin-x86_64'}[platform.system()]
    toolchain=ndk/'toolchains/llvm/prebuilt'/host
    compiler=toolchain/'bin/aarch64-linux-android29-clang'
    runner=runpy.run_path(str(ROOT/'scripts/port-package.py'))['package']
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
            if blob[:6]!=b'\x7fELF\x02\x01' or blob[18:20]!=b'\xb7\x00': raise ValueError('Expected arm64 ELF')
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
        payload['LICENSE.upstream']=(UPSTREAM/'LICENSE').read_bytes()
        receipt={'upstream':json.loads((MODULE/'UPSTREAM.json').read_text()),
                 'ndk':'28.2.13676358','runtime':'Android bionic; separate QVR child retained',
                 'status':'AZJ2 library identities verified; live capture/alignment not yet tested',
                 'source':{str(p.relative_to(UPSTREAM)):hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(UPSTREAM.rglob('*')) if p.is_file()}}
        payload['bin/build-info.json']=(json.dumps(receipt,indent=2,sort_keys=True)+'\n').encode()
        runner(args.output/'gxr-questlhsync-azj2-0.1.1-disabled.zip',payload,
               executables=['bin/'+binary for binary in builds])


if __name__=='__main__': main()
