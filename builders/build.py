"""Builds the code/*.atz modules (zstd-compressed compact SourceModule JSON).

    python3 -m builders [--check] [FILE.atz ...]   (run from the ecosystem root)

Writes each module whose JSON changed (unchanged files are left untouched). With `--check`, writes nothing and
exits non-zero if any file's JSON differs from what the builders produce. FILE arguments restrict the run.
"""

import argparse
import importlib
import pathlib
import subprocess
import sys

from .eco_mb import EcoMb
from .mb import module_json
from .root_mode import APP, IR

ZSTD_LEVEL = 19

# (file, builder module, extra builder args)
MODULES = [
    ("meta.atz", "meta", ()),
    ("llvm-ir-22.atz", "llvm_ir", ()),
    ("libc-2.42.atz", "libc", ()),
    ("spa-pod-1.6.atz", "spa_pod", ()),
    ("pipewire-1.6.atz", "pipewire", ()),
    ("synth-midi-sine.atz", "synth", (APP,)),
    ("synth-midi-sine-ir.atz", "synth", (IR,)),
    ("buzz-dsp.atz", "buzz_dsp", ()),
    ("buzz-samplegrid.atz", "buzz_sample_grid", ()),
    ("buzz-unwieldytracker.atz", "buzz_unwieldy_tracker", ()),
    ("buzz-m4.atz", "buzz_m4", ()),
    ("buzz-infector.atz", "buzz_infector", ()),
    ("buzz-tunaman.atz", "buzz_tuna_man", ()),
    ("buzz-ninja.atz", "buzz_ninja", ()),
    ("buzz-m4wii.atz", "buzz_m4wii", ()),
    ("buzz-classiceq.atz", "buzz_classic_eq", ()),
    ("buzz-karmafilter.atz", "buzz_karma_filter", ()),
    ("buzz-kaway.atz", "buzz_kaway", ()),
    ("buzz-bloodoverdrive.atz", "buzz_blood_overdrive", ()),
    ("buzz-bluecatphaser.atz", "buzz_blue_cat_phaser", ()),
    ("buzz-gunpowder-valentine.atz", "buzz_gunpowder", (APP,)),
    ("buzz-gunpowder-valentine-ir.atz", "buzz_gunpowder", (IR,)),
    ("wat-2.0.atz", "wat", ()),
    ("js-es2020.atz", "js", ()),
    ("webidl.atz", "webidl", ()),
    ("webidl-wasm.atz", "webidl_wasm", ()),
    ("webidl-js.atz", "webidl_js", ()),
    ("web-wasm.atz", "web_wasm", ()),
    ("hello-web.atz", "hello_web", ()),
    ("glsl-es-3.00.atz", "glsl", ()),
    ("webgl-uniforms.atz", "webgl_uniforms", ()),
    ("web-wiggle.atz", "web_wiggle", ()),
    ("wasi-0.1.atz", "wasi", ()),
    ("hello-wasi.atz", "hello_wasi", ("app",)),
    ("hello-wasi-wat.atz", "hello_wasi", ("wat",)),
    ("merman-ide.atz", "merman_ide", ()),
    ("stylus-recorder.atz", "stylus_recorder", ()),
]


def _decompress(path):
    return subprocess.run(["zstd", "-d", "-q", "-c", str(path)], check=True, capture_output=True).stdout.decode()


def _compress(text):
    return subprocess.run(
        ["zstd", f"-{ZSTD_LEVEL}", "-q", "-c"], input=text.encode(), check=True, capture_output=True
    ).stdout


def build_text(file):
    """The compact module JSON the builders produce for `file`."""
    for known_file, module_name, builder_args in MODULES:
        if known_file == file:
            builder = importlib.import_module("." + module_name, __package__)
            return module_json(builder.module(EcoMb(), *builder_args))
    raise KeyError(file)


def main():
    parser = argparse.ArgumentParser(prog="builders")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()
    known = {file for file, _, _ in MODULES}
    unknown = [f for f in args.files if f not in known]
    if unknown:
        parser.error("unknown module file(s): " + ", ".join(unknown))
    code = pathlib.Path(__file__).resolve().parent.parent / "code"
    mismatched = []
    for file, _, _ in MODULES:
        if args.files and file not in args.files:
            continue
        text = build_text(file)
        path = code / file
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
