"""Builds the code/<project>/*.atz modules (zstd-compressed compact SourceModule JSON).

    python3 -m builders [--check] [FILE.atz ...]   (run from the ecosystem root)

Writes each module whose JSON changed (unchanged files are left untouched). With `--check`, writes nothing and
exits non-zero if any file's JSON differs from what the builders produce. FILE arguments restrict the run. A
module whose builder package is not present (a project kept outside the repository) is skipped.
"""

import argparse
import importlib
import pathlib
import subprocess
import sys

from .eco_mb import EcoMb
from .mb import module_json
from .registry import modules

ZSTD_LEVEL = 19


def _decompress(path):
    return subprocess.run(["zstd", "-d", "-q", "-c", str(path)], check=True, capture_output=True).stdout.decode()


def _compress(text):
    return subprocess.run(
        ["zstd", f"-{ZSTD_LEVEL}", "-q", "-c"], input=text.encode(), check=True, capture_output=True
    ).stdout


def build_text(file):
    """The compact module JSON the builders produce for `file`, or None when its builder is absent."""
    for project, known_file, module_name, builder_args in modules():
        if known_file == file:
            name = __package__ + "." + project + "." + module_name
            try:
                builder = importlib.import_module(name)
            except ModuleNotFoundError as e:
                if e.name not in (name, __package__ + "." + project):
                    raise
                return None
            return module_json(builder.module(EcoMb(project), *builder_args))
    raise KeyError(file)


def main():
    parser = argparse.ArgumentParser(prog="builders")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()
    known = {file for _, file, _, _ in modules()}
    unknown = [f for f in args.files if f not in known]
    if unknown:
        parser.error("unknown module file(s): " + ", ".join(unknown))
    code = pathlib.Path(__file__).resolve().parent.parent / "code"
    mismatched = []
    for project, file, _, _ in modules():
        if args.files and file not in args.files:
            continue
        text = build_text(file)
        path = code / project / file
        if text is None:
            print(f"skipped (no builder): {file}", file=sys.stderr)
            continue
        if path.exists() and _decompress(path) == text:
            continue
        if args.check:
            mismatched.append(file)
            print(f"differs: {file}", file=sys.stderr)
        else:
            path.write_bytes(_compress(text))
            print(f"wrote: {file}")
    if mismatched:
        sys.exit(1)
