#!/usr/bin/env bash
set -euo pipefail
migration_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
migration_runtime=$(mktemp -d)
trap 'rm -rf -- "$migration_runtime"' EXIT
migration_ffmpeg=$("$migration_root/.venv/bin/python" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')
ln -s "$migration_ffmpeg" "$migration_runtime/ffmpeg"
export PATH="$migration_runtime:$PATH"
cd "$migration_root/demo"
npx --yes hyperframes@0.8.162 check
npx --yes hyperframes@0.8.162 render --fps 24 --quality standard --workers 2 --output "$migration_root/docs/legacy-migration-demo.mp4"
