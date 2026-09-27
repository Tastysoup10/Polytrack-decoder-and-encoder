#!/bin/bash
set -e
cd "$(dirname "$0")/.."

python3 -m pip install --upgrade pyinstaller
rm -rf build dist
python3 -m PyInstaller --clean --noconfirm Polytrack_linux.spec

echo "Built: dist/Polytrack"
