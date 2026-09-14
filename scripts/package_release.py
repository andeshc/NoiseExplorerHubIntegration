"""Package only original integration code, metadata and documentation."""

import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = root / "dist" / "noise_explorer-0.1.0.zip"
output.parent.mkdir(exist_ok=True)
files = [root / "README.md", *sorted((root / "docs").glob("*.md"))]
files += [
    path
    for path in (root / "custom_components" / "noise_explorer").rglob("*")
    if path.is_file()
    and "__pycache__" not in path.parts
    and path.suffix in {".py", ".json", ".yaml"}
]
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path, path.relative_to(root).as_posix())
with zipfile.ZipFile(output) as archive:
    assert archive.testzip() is None
    assert "custom_components/noise_explorer/manifest.json" in archive.namelist()
    assert not any(
        name.startswith("analysis/") or name.endswith((".apk", ".xapk", ".pyc"))
        for name in archive.namelist()
    )
print(f"Created {output.name}: {len(files)} files, {output.stat().st_size:,} bytes")
