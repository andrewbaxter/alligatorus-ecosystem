"""json-stdio-wasi.atz / json-stdio-libc.atz: json-<target>.atz specialized over stdio-<target>.atz, one per target
from this builder: a parser reading stdin and a writer writing stdout.

The module imports the reader and the sink, calls the const functions that generate the code, and exports the
results: `parser` ({type, raw, new, event}) and `writer` ({type, raw, new}). An app imports this module and uses
them like any target functions.
"""

WASM = "wasm"
LLVM = "llvm"

FILES = {WASM: "json-stdio-wasi.atz", LLVM: "json-stdio-libc.atz"}
STDIO = {WASM: "stdio-wasi.atz", LLVM: "stdio-libc.atz"}
JSON = {WASM: "json-wasm.atz", LLVM: "json-llvm.atz"}


def module(e, kind):
    top = []
    top.append(e.let("stdio", e.import_local("stdio", STDIO[kind])))
    top.append(e.let("json", e.import_local("json", JSON[kind])))
    top.append(
        e.let(
            "parser",
            e.call(
                e.fld(e.v("json"), "parser"), e.rec(e.p("name", e.s("stdio")), e.p("read", e.fld(e.v("stdio"), "read")))
            ),
        )
    )
    top.append(
        e.let(
            "writer",
            e.call(
                e.fld(e.v("json"), "writer"), e.rec(e.p("name", e.s("stdio")), e.p("write", e.fld(e.v("stdio"), "write")))
            ),
        )
    )
    top.append(e.ret(e.rec(e.p("parser", e.v("parser")), e.p("writer", e.v("writer")))))
    return top
