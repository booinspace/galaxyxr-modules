"""Trust-boundary checks for the one-click Steam Link APK builder."""
import copy
import hashlib
import io
from pathlib import Path
import runpy
import tempfile
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

ROOT=Path(__file__).resolve().parents[1]
api=runpy.run_path(str(ROOT/'companions/steamlink/build_steamlink.py'))


def fixture_patch(name, code=5001712, enabled=True):
    return {'name':name,'default':enabled,'compatiblePackages':[{
        'packageName':api['PACKAGE'],'targets':[{'version':'2.0.20',
        'versionCodes':{'ARM64_V8A':code},'isExperimental':False}]}]}


class SteamLinkBuilderTest(unittest.TestCase):
    def test_exact_build_and_root_profile(self):
        catalog={'patches':[fixture_patch(api['FACE_PATCH']),fixture_patch('OLED'),
            fixture_patch('Controller velocity frame'),fixture_patch('Experimental',enabled=False)]}
        info={'version':'2.0.20','code':5001712}
        self.assertEqual(api['selected_patches'](catalog,info),[api['FACE_PATCH'],'OLED'])
        for version,code in [('2.0.20',5001812),('2.0.24',5002389),('2.0.25',5002532)]:
            with self.subTest(code=code):
                self.assertEqual(api['selected_patches'](catalog,{'version':version,'code':code}),[])
        catalog['patches'][0]['compatiblePackages'][0]['targets'][0]['isExperimental']=True
        self.assertEqual(api['selected_patches'](catalog,info),[])

    def test_release_asset_origin_and_digest(self):
        release={'tag_name':'v1.0','assets':[{'name':'patches-1.0.mpp',
            'browser_download_url':'https://github.com/AngelDark92/xr-porting-hub/releases/download/v1.0/patches-1.0.mpp',
            'digest':'sha256:'+'a'*64}]}
        _,digest=api['asset_for'](release,r'patches-[0-9.]+\.mpp',api['PATCH_REPO'])
        self.assertEqual(digest,'a'*64)
        for key,value in [('digest',None),('browser_download_url','https://example.com/a.mpp'),
                ('browser_download_url','https://github.com/AngelDark92/xr-porting-hub/releases/download/v1.0/../bad.mpp')]:
            invalid=copy.deepcopy(release);invalid['assets'][0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                api['asset_for'](invalid,r'patches-[0-9.]+\.mpp',api['PATCH_REPO'])

    def test_only_published_original_links(self):
        text='[Steam Link 2.0.24](https://drive.google.com/file/d/AbC_123-/view?usp=sharing)\n'
        text+='[Steam Link 2.0.25](https://example.com/bad.apk)\n[4XVR 2.0.22](https://drive.google.com/file/d/Other/view)'
        self.assertEqual(api['drive_sources'](text),[('2.0.24','AbC_123-')])

    def test_failed_download_preserves_previous_file(self):
        download=api['download']
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'tool.zip';output.write_bytes(b'previous')
            expected=hashlib.sha256(b'correct').hexdigest()
            with patch.dict(download.__globals__,{'urlopen':lambda *a,**k:io.BytesIO(b'wrong')}):
                with self.assertRaisesRegex(ValueError,'checksum'):
                    download('https://example.com/tool.zip',output,expected)
            self.assertEqual(output.read_bytes(),b'previous')
            self.assertFalse(output.with_suffix('.zip.part').exists())
            with patch.dict(download.__globals__,{'urlopen':lambda *a,**k:io.BytesIO(b'correct')}):
                download('https://example.com/tool.zip',output,expected)
            self.assertEqual(output.read_bytes(),b'correct')

    def test_unpinned_original_is_refreshed(self):
        download=api['download']
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'original.apk';output.write_bytes(b'old')
            with patch.dict(download.__globals__,{'urlopen':lambda *a,**k:io.BytesIO(b'new')}):
                download('https://example.com/original.apk',output)
            self.assertEqual(output.read_bytes(),b'new')

    def test_tool_archive_cannot_escape_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)
            for name,mode in [('../escape',0o100644),('/absolute',0o100644),('link',0o120777)]:
                archive=base/'tool.zip'
                with ZipFile(archive,'w') as z:
                    info=ZipInfo(name);info.external_attr=mode<<16;z.writestr(info,b'x')
                with self.subTest(name=name),self.assertRaises(ValueError):
                    api['extract_depot_tool'](archive,base/'unpacked')
            self.assertFalse((base/'escape').exists())

    def test_unsigned_original_requires_pinned_hash_or_steam_provenance(self):
        verify=api['input_integrity']
        def unsigned(*args):
            raise subprocess.CalledProcessError(1,['apksigner'])
        info={'version':'2.0.20','code':5001712}
        pinned=next(iter(api['UNSIGNED_ORIGINALS']))
        with patch.dict(verify.__globals__,{'signer_digest':unsigned,'sha256':lambda p:pinned}):
            self.assertIn('pinned',verify(None,None,info,{'kind':'upstream original APK link'})['method'])
        with patch.dict(verify.__globals__,{'signer_digest':unsigned,'sha256':lambda p:'0'*64}):
            with self.assertRaisesRegex(ValueError,'no reviewed SHA-256'):
                verify(None,None,info,{'kind':'upstream original APK link'})
            self.assertIn('Steam depot',verify(None,None,info,{'kind':'Valve SteamVR depot'})['method'])

    def test_android_sdk_certificate_report_formats(self):
        digest='a'*64
        for text in ['Signer #1 certificate SHA-256 digest: '+digest+'\n',
                     'V2 Signer: certificate SHA-256 digest: '+digest+'\n']:
            with self.subTest(text=text),patch('subprocess.run',return_value=SimpleNamespace(stdout=text)):
                self.assertEqual(api['signer_digest']('apksigner','app.apk'),digest)
        text='V2 Signer: certificate SHA-256 digest: '+digest+'\nSigner #2 certificate SHA-256 digest: '+'b'*64+'\n'
        with patch('subprocess.run',return_value=SimpleNamespace(stdout=text)),self.assertRaises(ValueError):
            api['signer_digest']('apksigner','app.apk')


if __name__=='__main__': unittest.main()
