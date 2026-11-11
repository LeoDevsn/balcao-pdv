import hashlib
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from balcao import __version__


def main():
    target=ROOT/"dist"/f"Balcao-{__version__}.zip"
    target.parent.mkdir(parents=True,exist_ok=True)
    files=[ROOT/name for name in ("README.md","LICENSE","CHANGELOG.md","PRODUCT.md","DESIGN.md","QA.md","package.json","package-lock.json","pyproject.toml","iniciar.pyw",".gitignore")]
    for folder in ("balcao","tests","scripts"):
        files.extend(p for p in (ROOT/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    with zipfile.ZipFile(target,"x",compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path,Path("Balcao")/path.relative_to(ROOT))
    assets=[ROOT/"dist"/"Balcao.exe",target]
    (ROOT/"dist"/"SHA256SUMS.txt").write_text(''.join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in assets),encoding="ascii")
    print(target)


if __name__ == "__main__":
    main()
