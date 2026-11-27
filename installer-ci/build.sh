#!/usr/bin/env bash
set -euo pipefail
if [[ "$#" != 1 ]]; then
  printf 'usage: %s output-directory\n' "$0" >&2
  exit 2
fi
root="$(cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p -- "$1"
output="$(cd -- "$1" && pwd)"
generated="$(mktemp -d)"
trap 'rm -rf -- "$generated"' EXIT

python3 - "$root/src" "$generated" <<'PY'
import sys
from pathlib import Path

source, output = map(Path, sys.argv[1:])
replacements = (
    ('ModInstaller.swift', 'ModInstaller.swift',
     'FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("Mods")',
     'VerifyPaths.mods'),
    ('NativeOIV.m', 'NativeOIV.generated.m',
     '[[NSSearchPathForDirectoriesInDomains(NSCachesDirectory,NSUserDomainMask,YES).firstObject stringByAppendingPathComponent:@"ModsExpanded"] stringByStandardizingPath]',
     'verificationCache'),
)
for filename, generated, old, new in replacements:
    contents = (source / filename).read_text(encoding='utf-8')
    if contents.count(old) != 1:
        raise SystemExit(f'Standalone path override no longer matches {filename}')
    (output / generated).write_text(contents.replace(old, new), encoding='utf-8')
PY

sdk="$(xcrun --sdk macosx --show-sdk-path)"
xcrun clang -arch arm64 -mmacosx-version-min=13.0 -I "$root/src/libarchive" -c "$root/src/GameInstallerShim.c" -o "$generated/archive.o"
xcrun clang -arch arm64 -mmacosx-version-min=13.0 -c "$root/src/ModFileValidation.c" -o "$generated/validator.o"
xcrun swiftc -sdk "$sdk" -target arm64-apple-macosx13.0 -swift-version 5 -parse-as-library \
  -import-objc-header "$root/src/Bridge.h" \
  "$generated/ModInstaller.swift" "$root/src/Verify.swift" \
  "$generated/archive.o" "$generated/validator.o" -larchive -o "$output/verify-install"
xcrun clang -arch arm64 -mmacosx-version-min=13.0 -fobjc-arc -fblocks \
  -I "$generated" -I "$root/src" -framework Foundation -lz \
  "$root/src/VerifyOIV.m" -o "$output/verify-oiv"
