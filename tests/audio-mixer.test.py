"""Run the real Android-independent mixer ownership and lifecycle logic."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--java', required=True, type=Path)
parser.add_argument('--ecj', required=True, type=Path)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='gxr-mixer-test-') as directory:
    subprocess.run([str(args.java), '-jar', str(args.ecj), '-source', '1.8', '-target', '1.8',
                    '-proc:none', '-failOnWarning', '-d', directory,
                    str(ROOT / 'modules/audio-mixer/android/local/gxr/audio/MixerEngine.java'),
                    str(ROOT / 'tests/MixerEngineTest.java')], check=True)
    subprocess.run([str(args.java), '-cp', directory, 'MixerEngineTest'], check=True)
