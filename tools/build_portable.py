"""Build a Windows x64 portable release from a provisioned Python installation."""
from pathlib import Path
import importlib.metadata, sys, shutil, zipfile

def build(destination):
    if sys.platform != 'win32':
        raise SystemExit('Build on Windows with Python 3.12 x64')
    repository = Path(__file__).resolve().parents[1]
    destination = Path(destination).resolve()
    if destination.exists():
        raise SystemExit('Destination exists; choose a new output folder')
    destination.mkdir(parents=True)
    for pattern in ('*.py', '*.ps1', '*.html', '*.js', '*.css', '*.md'):
        for path in repository.glob(pattern):
            shutil.copy2(path, destination / path.name)
    runtime = destination / 'runtime'
    runtime.mkdir()
    base = Path(sys.base_prefix)
    for path in base.iterdir():
        if path.is_file() and (path.suffix in ('.exe', '.dll') or path.name.startswith('LICENSE')):
            shutil.copy2(path, runtime / path.name)
    shutil.copytree(base / 'DLLs', runtime / 'DLLs')
    shutil.copytree(base / 'Lib', runtime / 'Lib', ignore=shutil.ignore_patterns('site-packages', '__pycache__', 'test', 'tests', 'idlelib', 'tkinter', 'turtledemo'))
    packages = runtime / 'Lib' / 'site-packages'
    packages.mkdir()
    for name in ('Pillow', 'pypdfium2'):
        distribution = importlib.metadata.distribution(name)
        for entry in distribution.files:
            if '..' in entry.parts or '__pycache__' in entry.parts:
                continue
            source = Path(distribution.locate_file(entry))
            if source.is_file():
                target = packages / entry
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    (destination / 'Start.cmd').write_text('@echo off\ncd /d "%~dp0"\n"runtime\\python.exe" server.py\nif errorlevel 1 pause\n')
    (destination / 'inbox').mkdir()
    archive = destination.parent / (destination.name + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as out:
        for path in destination.rglob('*'):
            if path.is_file():
                out.write(path, str(Path(destination.name) / path.relative_to(destination)))
    print(archive)
if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else 'release/Aero-Inspection-Windows')
