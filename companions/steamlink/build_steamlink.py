"""Download the newest available compatible Steam Link VR APK and patch/sign it."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

PACKAGE = 'com.valvesoftware.steamlinkvr'
PATCH_REPO = 'AngelDark92/xr-porting-hub'
MORPHE_REPO = 'MorpheApp/morphe-desktop'
FACE_PATCH = 'GXR face and tongue bridge'
DEPOT_TAG = 'DepotDownloader_3.4.0'
DEPOT_SHA = 'a999dec66b4850fc961bd50366696d23c2d0fad7b18790e6a5647b2f19097a53'
APK_RELATIVE = 'drivers/vrlink/resources/android-steamlinkvr-release.apk'
# The upstream 2.0.20 original is unsigned; pin the exact base used for our first build.
UNSIGNED_ORIGINALS = {'85f655a70f2844d65572cf77c49936e441a7279377ecc49a78df2c8980d9926b': ('2.0.20', 5001712)}
# Match our rooted headset profile; avoid overlapping APK/root controller fixes.
ROOT_CONTROLLER_PATCHES = frozenset(('Controller velocity frame', 'Controller pose extrapolation',
    'Controller tracking from the controller HAL through Shizuku',
    'Controller grip haptics through Shizuku', 'Controller pose time'))
MAX_DOWNLOAD = 256 * 1024 * 1024


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def request(url):
    return Request(url, headers={'User-Agent': 'GalaxyXR-SteamLink-Builder', 'Accept': 'application/json' if url.startswith('https://api.github.com/') else '*/*'})


def text_from(url):
    with urlopen(request(url), timeout=45) as response:
        data = response.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError('Remote metadata exceeds size limit')
    return data.decode('utf-8')


def download(url, destination, expected_sha=None):
    destination = Path(destination)
    if expected_sha and destination.is_file() and sha256(destination) == expected_sha:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + '.part')
    try:
        with urlopen(request(url), timeout=60) as response, partial.open('wb') as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_DOWNLOAD:
                    raise ValueError('Download exceeds size limit')
                output.write(chunk)
        if expected_sha and sha256(partial) != expected_sha:
            raise ValueError('Download checksum mismatch: ' + destination.name)
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)
    return destination


def release(repo):
    data = json.loads(text_from('https://api.github.com/repos/' + repo + '/releases/latest'))
    if data.get('draft') or data.get('prerelease') or not re.fullmatch(r'[A-Za-z0-9._-]+', data.get('tag_name', '')):
        raise ValueError('Invalid stable release metadata: ' + repo)
    return data


def asset_for(data, pattern, repo):
    assets = [a for a in data['assets'] if re.fullmatch(pattern, a['name'])]
    if len(assets) != 1:
        raise ValueError('Expected exactly one release asset: ' + repo)
    asset = assets[0]
    digest = asset.get('digest') or ''
    prefix = 'https://github.com/' + repo + '/releases/download/' + data['tag_name'] + '/'
    if asset['browser_download_url'] != prefix + asset['name'] or not re.fullmatch(r'sha256:[a-fA-F0-9]{64}', digest):
        raise ValueError('Release lacks a trusted asset URL/SHA-256 digest: ' + repo)
    return asset, digest[7:].lower()


def wsl_path(value):
    if re.match(r'^[A-Za-z]:[\\/]', str(value)):
        return Path(subprocess.check_output(['wslpath', '-u', str(value)], text=True).strip())
    return Path(value).expanduser().resolve()


def sdk_tools():
    roots = [Path(v).expanduser() for k in ('ANDROID_HOME', 'ANDROID_SDK_ROOT') if (v := os.environ.get(k))]
    roots += [Path.home() / 'galaxy-xr-azj2/android-sdk', Path.home() / 'Android/Sdk']
    for root in roots:
        versions = sorted((root / 'build-tools').glob('*'), key=lambda p: tuple(map(int, re.findall(r'\d+', p.name))), reverse=True)
        for version in versions:
            aapt, signer = version / 'aapt2', version / 'apksigner'
            if all(p.is_file() and os.access(p, os.X_OK) for p in (aapt, signer)):
                return aapt, signer
    raise ValueError('Android SDK Build Tools with Linux aapt2 and apksigner are required in WSL. See README.md.')


def apk_identity(aapt, apk):
    result = subprocess.run([str(aapt), 'dump', 'badging', str(apk)], check=True, text=True, capture_output=True)
    match = re.search(r"^package: name='([^']+)' versionCode='([0-9]+)' versionName='([^']+)'", result.stdout, re.M)
    if not match or match[1] != PACKAGE:
        raise ValueError('Not a Steam Link VR APK: ' + str(apk))
    return {'package': match[1], 'code': int(match[2]), 'version': match[3]}


def package_info(aapt, apk):
    info = apk_identity(aapt, apk)
    with ZipFile(apk) as archive:
        if any('libgxr_' in n or 'XR_APILAYER_local_GalaxyXR_' in n for n in archive.namelist()):
            raise ValueError('Input APK is already patched; an original is required')
    return info


def compatible(patch, info):
    for package in patch.get('compatiblePackages') or []:
        if package.get('packageName') != PACKAGE:
            continue
        for target in package.get('targets') or []:
            if (not target.get('isExperimental', False) and target.get('version') == info['version']
                    and (target.get('versionCodes') or {}).get('ARM64_V8A') == info['code']):
                return True
    return False


def selected_patches(catalog, info):
    matches = [p for p in catalog['patches'] if compatible(p, info)]
    if not any(p['name'] == FACE_PATCH for p in matches):
        return []
    names = [p['name'] for p in matches if p.get('default') and p['name'] not in ROOT_CONTROLLER_PATCHES]
    if FACE_PATCH not in names:
        names.append(FACE_PATCH)
    if len(names) != len(set(names)):
        raise ValueError('Duplicate patch names in upstream catalog')
    return names


def extract_depot_tool(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive) as source:
        for entry in source.infolist():
            path = Path(entry.filename)
            mode = entry.external_attr >> 16
            if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or mode & 0o170000 == 0o120000:
                raise ValueError('Unsafe tool archive entry')
        source.extractall(destination)
    tool = destination / 'DepotDownloader'
    tool.chmod(0o755)
    return tool


def steam_apks(cache):
    archive = download('https://github.com/SteamRE/DepotDownloader/releases/download/' + DEPOT_TAG +
                       '/DepotDownloader-linux-x64.zip', cache / 'DepotDownloader-linux-x64.zip', DEPOT_SHA)
    tool = extract_depot_tool(archive, cache / DEPOT_TAG)
    filelist = cache / 'steam-filelist.txt'
    filelist.write_text(APK_RELATIVE + '\n')
    for branch in ('public', 'beta'):
        directory = cache / ('steamvr-' + branch)
        print('Checking Valve SteamVR ' + branch + ' APK…', flush=True)
        try:
            result = subprocess.run([str(tool), '-app', '250820', '-depot', '250824', '-branch', branch,
                '-os', 'windows', '-filelist', str(filelist), '-dir', str(directory), '-validate', '-max-downloads', '4'],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=240)
            (cache / ('steam-' + branch + '.log')).write_text(result.stdout)
            if result.returncode:
                raise ValueError('Steam depot download failed; see ' + str(cache / ('steam-' + branch + '.log')))
            apk = directory / APK_RELATIVE
            if not apk.is_file():
                raise ValueError('Valve depot did not contain the APK')
            yield apk, {'kind': 'Valve SteamVR depot', 'branch': branch, 'app': 250820, 'depot': 250824}
        except (subprocess.SubprocessError, ValueError) as error:
            print('  ' + str(error), flush=True)


def drive_sources(readme):
    # Only original APK links explicitly published in the upstream README.
    return re.findall(r'\[Steam Link ([0-9.]+)\]\(https://drive\.google\.com/file/d/([A-Za-z0-9_-]+)/view[^)]*\)', readme)


def source_apks(cache, readme, local_apk=None):
    if local_apk:
        yield wsl_path(local_apk), {'kind': 'user-supplied original'}
        return
    try:
        yield from steam_apks(cache)
    except (OSError, ValueError) as error:
        print('Valve download unavailable: ' + str(error), flush=True)
    for version, file_id in sorted(drive_sources(readme), key=lambda p: tuple(map(int, p[0].split('.'))), reverse=True):
        print('Checking upstream original APK link: ' + version, flush=True)
        try:
            url = 'https://drive.usercontent.google.com/download?' + urlencode({'id': file_id, 'export': 'download', 'confirm': 't'})
            apk = download(url, cache / ('upstream-' + file_id + '.apk'))
            with ZipFile(apk) as archive:
                if archive.testzip() is not None:
                    raise ValueError('Invalid APK ZIP')
            yield apk, {'kind': 'upstream original APK link', 'version_label': version, 'file_id': file_id}
        except (OSError, ValueError, BadZipFile) as error:
            print('  Link unavailable: ' + str(error), flush=True)
            (cache / ('upstream-' + file_id + '.apk')).unlink(missing_ok=True)


def signer_digest(signer, apk):
    result = subprocess.run([str(signer), 'verify', '--print-certs', str(apk)], check=True, capture_output=True, text=True)
    digests = {value.lower() for value in re.findall(r'certificate SHA-256 digest: ([a-fA-F0-9]{64})\s*$', result.stdout, re.M)}
    if len(digests) != 1:
        raise ValueError('Expected one unique signing certificate in apksigner output')
    return digests.pop()


def input_integrity(signer, apk, info, origin):
    try:
        return {'method': 'APK signature integrity', 'certificate_sha256': signer_digest(signer, apk)}
    except subprocess.CalledProcessError:
        if origin.get('kind') == 'Valve SteamVR depot':
            return {'method': 'official Steam depot chunk verification'}
        if UNSIGNED_ORIGINALS.get(sha256(apk)) == (info['version'], info['code']):
            print('  Unsigned upstream base matches the pinned original SHA-256', flush=True)
            return {'method': 'pinned unsigned upstream original SHA-256'}
        raise ValueError('Unsigned original has no reviewed SHA-256; refusing to patch it')


def build(args):
    aapt, signer = sdk_tools()
    java = shutil.which('java')
    if not java:
        raise ValueError('Java 21 or newer is required in WSL')
    result = subprocess.run([java, '-version'], capture_output=True, text=True, check=True)
    match = re.search(r'version "([0-9]+)', result.stderr + result.stdout)
    if not match or int(match[1]) < 21:
        raise ValueError('Java 21 or newer is required in WSL')
    legacy = Path.home() / 'galaxy-xr-azj2/steamlink-install'
    if not args.morphe_data and (legacy / 'SteamLink-2.0.20-5001712-GalaxyXR.apk').is_file() and not (legacy / 'morphe-data/morphe.keystore').is_file():
        raise ValueError('Your previous signing key is missing. Restore it; refusing to generate a different key.')
    cache = Path.home() / '.cache/galaxyxr-steamlink'
    cache.mkdir(parents=True, exist_ok=True)
    patches_release, morphe_release = release(PATCH_REPO), release(MORPHE_REPO)
    bundle_asset, bundle_sha = asset_for(patches_release, r'patches-[0-9.]+\.mpp', PATCH_REPO)
    morphe_asset, morphe_sha = asset_for(morphe_release, r'morphe-desktop-[0-9.]+-all\.jar', MORPHE_REPO)
    tag = patches_release['tag_name']
    base = 'https://raw.githubusercontent.com/' + PATCH_REPO + '/' + tag + '/'
    catalog = json.loads(text_from(base + 'patches-list-all.json'))
    if catalog.get('version') != tag.removeprefix('v') or catalog.get('channel') != 'all':
        raise ValueError('Release/catalog version mismatch')
    readme = text_from(base + 'README.md')
    bundle = download(bundle_asset['browser_download_url'], cache / bundle_asset['name'], bundle_sha)
    jar = download(morphe_asset['browser_download_url'], cache / morphe_asset['name'], morphe_sha)
    candidates = []
    for apk, origin in source_apks(cache, readme, args.apk):
        try:
            info = package_info(aapt, apk)
            names = selected_patches(catalog, info)
            print('  Steam Link ' + info['version'] + '/' + str(info['code']) + (' supported' if names else ' unsupported; skipping'), flush=True)
            if names:
                integrity = input_integrity(signer, apk, info, origin)
                candidates.append((info['code'], apk, info, {**origin, 'integrity': integrity}, names))
        except (OSError, ValueError, BadZipFile, subprocess.SubprocessError) as error:
            print('  Rejected input: ' + str(error), flush=True)
    if not candidates:
        raise ValueError('No downloadable original APK matches the released patches. Supply an exact supported original using --apk PATH.')
    _, apk, info, origin, names = max(candidates, key=lambda c: c[0])
    print('Building newest available compatible APK: ' + info['version'] + '/' + str(info['code']), flush=True)
    data = wsl_path(args.morphe_data) if args.morphe_data else (
        legacy / 'morphe-data' if (legacy / 'morphe-data/morphe.keystore').is_file() else Path.home() / '.local/share/galaxyxr-steamlink/morphe-data')
    data.mkdir(parents=True, exist_ok=True)
    data.chmod(0o700)
    keystore = data / 'morphe.keystore'
    key_before = sha256(keystore) if keystore.is_file() else None
    if args.morphe_data and key_before is None:
        raise ValueError('The selected Morphe data directory has no signing key; refusing to generate a replacement')
    env = {**os.environ, 'MORPHE_DATA_DIR': str(data)}
    output = wsl_path(args.output)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-UTC')
    destination = output / stamp
    with tempfile.TemporaryDirectory(prefix='patch-', dir=cache) as temporary:
        work = Path(temporary)
        built, report = work / 'SteamLink-GalaxyXR.apk', work / 'patch-result.json'
        command = [java, '-jar', str(jar), 'patch', '-p', str(bundle), '--exclusive']
        for name in names:
            command += ['--enable=' + name]
        command += ['-o', str(built), '-r', str(report), str(apk)]
        subprocess.run(command, env=env, stdin=subprocess.DEVNULL, check=True)
        patched = json.loads(report.read_text())
        if (patched.get('success') is not True or patched.get('failedPatches') or patched.get('packageName') != PACKAGE
                or patched.get('packageVersion') != info['version'] or set(patched.get('appliedPatches', [])) != set(names)):
            raise ValueError('Morphe did not apply the complete requested patch set')
        if apk_identity(aapt, built) != info:
            raise ValueError('Built APK package/version changed unexpectedly')
        with ZipFile(built) as archive, ZipFile(bundle) as resources:
            for apk_name, resource_name in [
                ('lib/arm64-v8a/libgxr_face_bridge.so', 'steamlink/androidxr/libgxr_face_bridge.so'),
                ('assets/openxr/1/api_layers/implicit.d/XR_APILAYER_local_GalaxyXR_face_bridge.json', 'steamlink/androidxr/XR_APILAYER_local_GalaxyXR_face_bridge.json')]:
                if archive.read(apk_name) != resources.read(resource_name):
                    raise ValueError('Built APK does not contain the released face bridge')
        certificate = signer_digest(signer, built)
        previous = legacy / 'SteamLink-2.0.20-5001712-GalaxyXR.apk'
        if data == legacy / 'morphe-data' and previous.is_file() and signer_digest(signer, previous) != certificate:
            raise ValueError('Signing certificate changed; APK would not update your installed build')
        if key_before and sha256(keystore) != key_before:
            raise ValueError('Existing signing key unexpectedly changed')
        destination.mkdir(parents=True, exist_ok=False)
        filename = 'SteamLink-' + info['version'] + '-' + str(info['code']) + '-GalaxyXR-patches-' + tag.removeprefix('v') + '.apk'
        final = destination / filename
        shutil.copyfile(built, final)
        shutil.copyfile(report, destination / 'patch-result.json')
        receipt = {'built_utc': stamp, 'apk': info, 'source': origin, 'original_sha256': sha256(apk),
            'patch_release': patches_release['html_url'], 'patch_bundle_sha256': bundle_sha,
            'morphe_release': morphe_release['html_url'], 'morphe_jar_sha256': morphe_sha,
            'selected_patches': names, 'root_profile_exclusions': sorted(ROOT_CONTROLLER_PATCHES),
            'signer_certificate_sha256': certificate, 'apk_sha256': sha256(final)}
        (destination / 'build-info.json').write_text(json.dumps(receipt, indent=2) + '\n')
        (destination / (filename + '.sha256')).write_text(receipt['apk_sha256'] + '  ' + filename + '\n')
    print('\nBUILT: ' + str(final), flush=True)
    print('No headset installation was performed. Keep your Morphe signing data private and backed up.', flush=True)
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='output', help='Windows or Linux output directory')
    parser.add_argument('--apk', help='Use a supplied original instead of automatic downloads')
    parser.add_argument('--morphe-data', help='Existing Morphe data directory containing morphe.keystore')
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        print('Python 3.11 or newer is required in WSL.', file=sys.stderr)
        return 1
    try:
        build(args)
    except (OSError, ValueError, KeyError, BadZipFile, subprocess.SubprocessError) as error:
        print('\nERROR: ' + str(error), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
