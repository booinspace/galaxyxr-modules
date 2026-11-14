"""Build the AZJ2 Framebuffer10 port from a pinned 4uva4ek source checkout.

No stock or generated Samsung library is packaged. The reviewed edit script is
byte-identical on AZJ2; the controller verifies the new input/output hashes.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
from zipfile import ZipFile

from gxr_build import export_source, package, replace_exact as replace

ROOT=Path(__file__).resolve().parents[1]
COMMIT='9f096dfc79e72f180410bcfa5ba32b566734f62b'
URL='https://github.com/4uva4ek/galaxyxr-modules.git'
STOCK='bd51da246ce12452b0069f3fc35a24389b7705c33819e37ab1916c5a6b3e8cd7'
PATCHED='3869de4f1b2d46f607089486a3b35997b15ebff0be7b9082d6af6d2a2eb64caf'
EDIT_SCRIPT='f9aef5110e1ea6acad72bfb20b36aab5668491d0666d3d3111d8b511c418668a'


def port(source):
    native=source/'modules/framebuffer10/native/main.cpp'
    if hashlib.sha256(native.with_name('payload_patch.inc').read_bytes()).hexdigest()!=EDIT_SCRIPT:
        raise ValueError('Unreviewed shader edit script')
    replace(native,'54f9c32c6a80198dff06ae8cda56a0f81d87b660c67f62bc452725f241e0733e',STOCK)
    replace(native,'f8e5cfeb7aefeabf922315eb8ca13a71a95df686ac85e3b6742d3ddb2964c142',PATCHED)
    replace(native,'static volatile sig_atomic_t interrupted=0;', '''static bool azj2Firmware(){
    char fp[PROP_VALUE_MAX]{};__system_property_get("ro.build.fingerprint",fp);
    return !strcmp(fp,"samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys");
}
static volatile sig_atomic_t interrupted=0;''')
    replace(native,'static int buildPayload(){', 'static int buildPayload(){\n    if(!azj2Firmware()){puts("AZJ2 firmware required");return 2;}')
    replace(native,'    if(geteuid()!=0){puts("DISABLED - root required");return false;}',
            '    if(geteuid()!=0){puts("DISABLED - root required");return false;}\n    if(!azj2Firmware()){puts("DISABLED - AZJ2 required");return false;}')
    replace(native,'    bool softRestartRequested(){', '''    bool coordinatorBusy(){return mock?scenario=="coordinator-busy-recovery":access("/dev/ksu-restart-stage/busy",F_OK)==0;}
    bool softRestartRequested(){''')
    replace(native,'access((std::string(DIR)+"/soft-restart").c_str(),F_OK)==0;}',
            'access((std::string(DIR)+"/soft-restart").c_str(),F_OK)==0 || (coordinatorBusy()&&preferenceOff());}')
    replace(native,'    // No future trial write can occur: this supervisor is the only writer.',
            '''    if(b.coordinatorBusy()){
        b.report("DISABLED","KernelSU restart owns Android; no independent recovery restart; verify or fully reboot");
        return false;
    }
    // No future trial write can occur: this supervisor is the only writer.''')
    replace(native,'access((std::string(DIR)+"/coordinated-restart").c_str(),F_OK)==0;',
            'access((std::string(DIR)+"/coordinated-restart").c_str(),F_OK)==0 || b.coordinatorBusy();')
    replace(native,'        int pid=b.mock?124:sfpid();',
            '        if(coordinated){b.pause(100);continue;}\n        int pid=b.mock?124:sfpid();')
    replace(native,'access((std::string(DIR)+"/stop").c_str(),F_OK)==0);}',
            'access((std::string(DIR)+"/stop").c_str(),F_OK)==0) || (mock&&scenario=="coordinator-busy-recovery"&&time>=20000);}')
    replace(native,'const std::vector<std::string> allowed={"normal",',
            'const std::vector<std::string> allowed={"coordinator-busy-recovery","normal",')
    auto=source/'modules/framebuffer10/module/auto.sh'
    replace(auto,'MODDIR=$(CDPATH= cd -P "${0%/*}" && pwd)', 'MODDIR=$(CDPATH=\'\' cd -P "${0%/*}" && pwd)')
    replace(auto,' enable|resume|resume-coordinated) sh', ' status|disable|enable|resume|resume-coordinated) sh')
    text=auto.read_text()
    a=text.index(' disable)\n'); b=text.index(' *) echo',a)
    text=text[:a]+''' disable)
  : > "$MODDIR/disable" || fail 'Cannot save disable preference'
  if [ -d "$LEASE" ]; then
   echo 'DISABLED - Uncheck, then use one KernelSU GXR Soft restart to restore stock output safely.'
   exit 1
  fi
  echo 'DISABLED - no module session'
  ;;
'''+text[b:]
    auto.write_text(text)
    props=source/'modules/framebuffer10/module/module.prop'
    props.write_text('id=gxr_framebuffer10\nname=Galaxy XR Framebuffer10 (AZJ2)\nversion=0.1.0-azj2-experimental\nversionCode=10001\nauthor=4uva4ek; AZJ2 port by booinspace\ndescription=10-bit SDR colour output with locally generated shader fixes. AZJ2 only; installs disabled. Apply and remove through one GXR Soft restart. No HDR and no vendor binaries bundled.\n')
    config=source/'modules/framebuffer10/build.json'
    import json
    d=json.loads(config.read_text());d['files'].remove('customize.sh');config.write_text(json.dumps(d,indent=2)+'\n')
    hook=source/'modules/framebuffer10/module/restart-hooks.sh'
    replace(hook,'START=$(date +%s)', "START=$(awk '{print int($1)}' /proc/uptime)")
    replace(hook,'$(date +%s) - START', "$(awk '{print int($1)}' /proc/uptime) - START")
    for name in ('action.sh',): shutil.copyfile(ROOT/'modules/framebuffer10'/name,source/'modules/framebuffer10/module'/name)
    native.with_name('AZJ2-port.txt').write_text('Source '+URL+' at '+COMMIT+'\nStock '+STOCK+'\nGenerated '+PATCHED+'\nShader edit script '+EDIT_SCRIPT+'\n')
    return source


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ndk',required=True,type=Path)
    ap.add_argument('--upstream',type=Path,help='Clean checkout at the exact pinned commit')
    ap.add_argument('--output',type=Path,default=ROOT/'releases')
    args=ap.parse_args()
    if args.upstream:
        head=subprocess.check_output(['git','-C',str(args.upstream),'rev-parse','HEAD'],text=True).strip()
        if head!=COMMIT: ap.error('Pinned upstream commit required')
        subprocess.run(['git','-C',str(args.upstream),'diff','--quiet','HEAD'],check=True)
    with tempfile.TemporaryDirectory(prefix='gxr-fb10-azj2-') as temporary:
        work=Path(temporary)/'source'
        export_source(work,URL,COMMIT,checkout=args.upstream)
        port(work)
        subprocess.run(['python3',str(work/'tools/build.py'),'framebuffer10','--ndk',str(args.ndk.resolve())],check=True,cwd=work)
        result,= (work/'dist/framebuffer10').glob('*.zip')
        with ZipFile(result) as archive: payload={n:archive.read(n) for n in archive.namelist()}
        payload['README.md']=(ROOT/'modules/framebuffer10/README.md').read_bytes()
        payload['README.txt']=payload['README.md']
        payload['NOTICE.txt'] += b'\nAZJ2 port by booinspace. Source and generated library hashes differ from AZF3; see README.md.\n'
        payload['bin/source/build-framebuffer10-azj2.py']=Path(__file__).read_bytes()
        payload['bin/source/port-package.py']=(ROOT/'scripts/port-package.py').read_bytes()
        payload['bin/source/framebuffer10-azj2-controller.cpp']=(work/'modules/framebuffer10/native/main.cpp').read_bytes()
        payload['bin/source/AZJ2-port.txt']=(work/'modules/framebuffer10/native/AZJ2-port.txt').read_bytes()
        payload['bin/source/gxr_build.py']=(ROOT/'scripts/gxr_build.py').read_bytes()
        package(
            args.output/'gxr-framebuffer10-azj2-0.1.0-disabled.zip',payload,executables=['bin/gxr-fb10-gate'])


if __name__=='__main__':main()
