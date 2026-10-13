# alligatorus-ecosystem

Modules for the [alligatorus](https://github.com/andrewbaxter/alligatorus) compiler: targets (llvm
ir, wat, js, glsl), bindings (libc, wasi, pipewire, webidl, the merman editor), memory and collection
libraries, and apps built on them.

- `code/<project>/*.atz` are the modules, zstd-compressed compact SourceModule JSON. Each is a root
  `at build` or `at run` takes.
- `builders/<project>/` are the python packages that produce them, listed in `builders/registry.py`:
  `python3 -m builders` rewrites every module whose JSON changed, `python3 -m builders --check`
  verifies they are up to date.
- `tests/` runs the apps: `python3 -m tests` runs every case group under `tests/cases` with `at run`
  (an `apps` file names the apps, each `NAME.in` is fed to them to produce `NAME.out` with the status
  in `NAME.status`, and a `build-fails` file names modules that must fail to build);
  `python3 -m tests --build` first builds every root. The compiler is `at` on PATH or the command
  `AT` names.

CI builds the compiler from the alligatorus repository (from the branch named like the one under
test when it exists, else master), checks the modules, builds every root and runs the tests.
