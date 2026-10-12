#!/usr/bin/env python3
"""Fetch the CC0 MakeHuman body data the character kit is built from.

MPFB2 (the MakeHuman add-on for Blender) ships its assets under CC0 1.0:
the base mesh, the shape targets behind every slider, the game-engine rig
and its skin weights (see LICENSE.md, part C, in the MPFB2 repository).
Its program code is GPL-3.0; none of that code is fetched or used here.

The files come from one pinned MPFB2 commit and are checked against the
SHA-256 values in mpfb2_cc0_sources.json, so a rebuild reads exactly the
bytes the committed GLBs were built from. They land in a cache outside the
repo (default ~/.cache/thistletide/mpfb2/<commit>); nothing is committed.

Usage:
    fetch_mpfb2_cc0.py                 # fetch anything missing, verify all
    fetch_mpfb2_cc0.py --print-dir     # fetch, then print the cache dir
    fetch_mpfb2_cc0.py --update-hashes # re-hash after editing the file list
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "mpfb2_cc0_sources.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_dir(manifest: dict) -> Path:
    root = os.environ.get("TT_MPFB2_CACHE") or Path.home() / ".cache" / "thistletide" / "mpfb2"
    return Path(root) / manifest["commit"]


def fetch(update_hashes: bool = False) -> Path:
    manifest = json.loads(MANIFEST.read_text())
    base = cache_dir(manifest)
    url = f"https://raw.githubusercontent.com/{manifest['repository']}/{manifest['commit']}/"
    files: dict[str, str] = manifest["files"]
    for rel, want in files.items():
        path = base / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".part")
            with urllib.request.urlopen(url + rel, timeout=60) as response, tmp.open("wb") as out:
                out.write(response.read())
            tmp.replace(path)
        got = sha256_of(path)
        if update_hashes:
            files[rel] = got
        elif got != want:
            raise SystemExit(f"{rel}: sha256 {got} does not match the manifest ({want}). "
                             "Delete the cache file to refetch, or run --update-hashes after a deliberate change.")
    if update_hashes:
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--update-hashes", action="store_true")
    parser.add_argument("--print-dir", action="store_true")
    args = parser.parse_args()
    base = fetch(args.update_hashes)
    if args.print_dir:
        print(base)
    else:
        print(f"MPFB2 CC0 data ready in {base}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
