"""Generate KernelSU GXR feeds from checksum-verified, published release assets."""
import argparse
import io
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

from gxr_build import sha256, validate_package

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'booinspace/galaxyxr-modules'
RAW = f'https://raw.githubusercontent.com/{REPOSITORY}/main'
MAX_ZIP = 128 * 1024 * 1024


def download(url, limit):
    request = urllib.request.Request(url, headers={'User-Agent': 'galaxyxr-module-catalogue'})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Download exceeds size limit: ' + url)
    return data


def build_catalogue(releases, load):
    selected = {}
    for release in releases:
        if release['draft']:
            raise ValueError('Cannot publish a draft release in the catalogue')
        for asset in release['assets']:
            name = asset['name']
            if not name.startswith('gxr-') or not name.endswith('.zip') or name.endswith('-windows.zip'):
                continue
            if not re.fullmatch(r'[A-Za-z0-9._-]+', name) or not 0 < asset['size'] <= MAX_ZIP:
                raise ValueError('Invalid module asset: ' + name)
            url = asset['browser_download_url']
            if not url.startswith(f'https://github.com/{REPOSITORY}/releases/download/'):
                raise ValueError('Module URL is outside the published release')
            digest = (asset.get('digest') or '').removeprefix('sha256:')
            if not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError('Published SHA-256 is required: ' + name)
            blob = load(asset)
            if len(blob) != asset['size'] or sha256(blob) != digest:
                raise ValueError('Published asset checksum/size mismatch: ' + name)
            payload = validate_package(io.BytesIO(blob))
            lines = [line.split('=', 1) for line in payload['module.prop'].decode().splitlines()
                     if '=' in line and not line.startswith('#')]
            props = dict(lines)
            if len(props) != len(lines):
                raise ValueError('Duplicate module property: ' + name)
            identity = props['id']
            # Retired standalone Rotation must not be offered beside Window Controls.
            if identity == 'gxr_window_rotation':
                continue
            code = int(props['versionCode'])
            if code <= 0:
                raise ValueError('Invalid module versionCode: ' + name)
            feed = {'version': props['version'], 'versionCode': code, 'zipUrl': url,
                    'sha256': digest, 'changelog': RAW + '/README.md'}
            entry = {'id': identity, 'name': props['name'], 'author': props.get('author', ''),
                     'description': 'SM-I610 AZJ2. ' + props.get('description', ''),
                     'updateJson': f'{RAW}/updates/{identity}.json',
                     'experimental': bool(release['prerelease'])}
            previous = selected.get(identity)
            if previous and previous[1]['versionCode'] == code and previous[1]['sha256'] != digest:
                raise ValueError('Different payloads share a module versionCode: ' + identity)
            if previous is None or previous[1]['versionCode'] < code:
                selected[identity] = (entry, feed)
    if not selected:
        raise ValueError('No installable headset modules found')
    return ({'schemaVersion': 1, 'modules': [selected[key][0] for key in sorted(selected)]},
            {key: selected[key][1] for key in sorted(selected)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', action='append', required=True, help='Published tag; repeat for separate module releases')
    parser.add_argument('--cache', type=Path, default=ROOT / '.build/catalogue')
    args = parser.parse_args()
    releases = [json.loads(download(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/' +
                urllib.parse.quote(tag, safe=''), 2 * 1024 * 1024)) for tag in args.release]
    args.cache.mkdir(parents=True, exist_ok=True)

    def load(asset):
        expected = asset['digest'].removeprefix('sha256:')
        for path in (ROOT / 'releases' / asset['name'], args.cache / asset['name']):
            if path.is_file() and path.stat().st_size == asset['size']:
                data = path.read_bytes()
                if sha256(data) == expected:
                    return data
        data = download(asset['browser_download_url'], MAX_ZIP)
        if sha256(data) != expected or len(data) != asset['size']:
            raise ValueError('Published asset checksum/size mismatch: ' + asset['name'])
        (args.cache / asset['name']).write_bytes(data)
        return data

    catalogue, feeds = build_catalogue(releases, load)
    output = ROOT / 'updates'
    output.mkdir(exist_ok=True)
    for identity, feed in feeds.items():
        (output / (identity + '.json')).write_text(json.dumps(feed, indent=2) + '\n')
    (ROOT / 'modules.json').write_text(json.dumps(catalogue, indent=2) + '\n')
    print(f'Generated modules.json and {len(feeds)} feeds from published, checksum-verified headset ZIPs.')


if __name__ == '__main__':
    main()
