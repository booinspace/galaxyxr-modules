"""Build native app-volume controls and the left-pinch shortcut in the shared AZJ2 runtime."""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    subprocess.run([sys.executable, str(Path(__file__).with_name('build-audio-mixer-azj2.py')),
                    '--quick-settings-gesture', *sys.argv[1:]], check=True)
