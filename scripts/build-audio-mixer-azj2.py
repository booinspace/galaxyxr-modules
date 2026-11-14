"""Build Audio Mixer inside Window Controls' single AZJ2 SystemUI runtime."""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    subprocess.run([sys.executable, str(Path(__file__).with_name('build-window-curvature-azj2.py')),
                    '--integrated-borderless', '--integrated-rotation', '--no-borderless-delay',
                    '--no-startup-age', '--audio-mixer', *sys.argv[1:]], check=True)
