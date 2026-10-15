"""Builds every root module and runs the app cases under tests/cases with `at run`.

    python3 -m tests            (run from the ecosystem root)
    python3 -m tests --build    also build every code/<project>/*.atz first
    python3 -m tests GROUP ...  only these case groups

A case group is a directory tests/cases/GROUP holding cases; its optional `apps` file (one code/ module per line, as
`<project>/<file>.atz`: the apps the group's cases run against) and, per case NAME, NAME.in (stdin), NAME.out
(the stdout the app must produce) and optionally NAME.status (the exit status it must end with, 0 when
absent). A case with a NAME.app file runs only on the module that file names, instead of the group's apps. A
group may instead (or also) hold a `build-fails` file naming modules that must fail to build: those are left
out of the `--build` pass and each is checked to fail.

The compiler is the `at` command on PATH, or the one `AT` names.
"""

import argparse
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES = ROOT / "tests" / "cases"
CODE = ROOT / "code"


def _at():
    return os.environ.get("AT", "at")


def _lines(path):
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def _groups():
    """Every directory under tests/cases holding cases (`*.in`), an `apps` file or a `build-fails` file."""
    return sorted(
        p.name
        for p in CASES.iterdir()
        if p.is_dir() and (any(p.glob("*.in")) or (p / "apps").exists() or (p / "build-fails").exists())
    )


def build_roots(skip):
    """Builds every root module but those in `skip`; a module that fails to build fails the run."""
    failed = []
    for path in sorted(CODE.glob("*/*.atz")):
        name = path.relative_to(CODE).as_posix()
        if name in skip:
            continue
        print(f"build: {name}", flush=True)
        r = subprocess.run([_at(), "build", str(path)], capture_output=True, text=True)
        if r.returncode != 0:
            failed.append(name)
            print(r.stdout, end="")
            print(r.stderr, end="", file=sys.stderr)
            print(f"FAIL build: {name}", flush=True)
    return failed


def run_group(group):
    failed = []
    group_dir = CASES / group
    for app in _lines(group_dir / "build-fails"):
        name = f"{group}: {app} must fail to build"
        r = subprocess.run([_at(), "build", str(CODE / app)], capture_output=True, text=True)
        if r.returncode == 0:
            failed.append(name)
            print(f"FAIL {name}")
        else:
            print(f"ok   {name}")
        sys.stdout.flush()
    apps = _lines(group_dir / "apps")
    for case in sorted(p.stem for p in group_dir.glob("*.in")):
        app_path = group_dir / (case + ".app")
        for app in _lines(app_path) if app_path.exists() else apps:
            name = f"{group}/{case} on {app}"
            stdin = (group_dir / (case + ".in")).read_bytes()
            want_out = (group_dir / (case + ".out")).read_bytes()
            status_path = group_dir / (case + ".status")
            want_status = int(status_path.read_text().strip()) if status_path.exists() else 0
            r = subprocess.run([_at(), "run", str(CODE / app)], input=stdin, capture_output=True)
            if r.returncode != want_status or r.stdout != want_out:
                failed.append(name)
                print(f"FAIL {name}: status {r.returncode} (want {want_status})")
                print(f"  stdout: {r.stdout!r}")
                print(f"  want:   {want_out!r}")
                if r.returncode != want_status:
                    print("  stderr: " + r.stderr.decode(errors="replace").strip().replace("\n", "\n          "))
            else:
                print(f"ok   {name}")
            sys.stdout.flush()
    return failed


def main():
    parser = argparse.ArgumentParser(prog="tests")
    parser.add_argument("--build", action="store_true", help="build every root module first")
    parser.add_argument("groups", nargs="*")
    args = parser.parse_args()
    all_groups = _groups()
    unknown = [g for g in args.groups if g not in all_groups]
    if unknown:
        parser.error("unknown case group(s): " + ", ".join(unknown))
    failed = []
    if args.build:
        skip = {app for g in all_groups for app in _lines(CASES / g / "build-fails")}
        failed.extend("build " + f for f in build_roots(skip))
    for group in args.groups or all_groups:
        failed.extend(run_group(group))
    if failed:
        print(f"{len(failed)} failed:")
        for f in failed:
            print("  " + f)
        sys.exit(1)
    print("all passed")
