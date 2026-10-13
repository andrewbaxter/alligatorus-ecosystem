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

## json

`json.atz` is the parsing and serializing logic of json, belonging to no target: const functions that stage it
over a record of ops (the event constructors, a reader, the target's int and byte types, and a state value
whose fields are the parser's registers and byte vecs). Nothing in it is staged per use.

`json-wasm.atz` and `json-llvm.atz` give that logic a representation on each target, from one builder:
`parser({name, read})` yields owned parser handles (destructor.atz) over a constant reader function, and
`writer({name, write})` owned writer handles over a constant sink; their `_new`, `_free`, `_next` and writer
piece functions are dependencies (`func_dep`), defined once per reader or sink however many parsers or writers a
module makes. A parser's `next()` consumes one value or structural token and yields an event of a per-target
union (`end`, `error(code)`, `null`, `bool(v)`, `number(s)`, `string(s)`, `key(s)` and the container events;
`s` a byte slice of the parser's data vec), read with `match`. There is no depth limit. `slice_reader` reads a
document in memory and `vec_writer` collects output in a byte vec.

The apps `json-echo-wasi.atz` and `json-echo-libc.atz` read a document from stdin and write it back out
compactly; `json-two-*.atz` parse two documents at once through one parser definition.
