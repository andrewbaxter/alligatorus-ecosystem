"""json-echo-wasi.atz / json-echo-libc.atz: apps reading a json document from stdin and writing it back out
compactly, one per target from this builder.

Each app imports json-stdio-<target>.atz (a parser over stdin and a writer over stdout) and stdio-<target>.atz
(for the raw byte sink and the exit), and loops matching each event of the document into the writer. A malformed
document prints `json error <code>` and exits with status 1.
"""

from ..root_mode import APP, root_mode_finish
from ..wasm.wat import bind_types
from . import json_stdio

WASM = "wasm"
LLVM = "llvm"

FILES = {WASM: "json-echo-wasi.atz", LLVM: "json-echo-libc.atz"}

ERROR_TEXT = "json error "


def _lo(e, name):
    return e.lower(e.v(name))


def _stdio(e, name):
    return e.lower(e.fld(e.v("stdio"), name))


def _json_lets(e, top, kind):
    top.append(e.let("stdio", e.import_local("stdio", json_stdio.STDIO[kind])))
    top.append(e.let("js", e.import_local("js", json_stdio.FILES[kind])))
    for obj in ["parser", "writer"]:
        for f in ["type", "new"]:
            top.append(e.let(f"{obj}_{f}", e.fld(e.fld(e.v("js"), obj), f)))


def _echo(e, null, on_error):
    """The parse loop: every event of the document into the writer; `on_error(code)` reports and exits."""

    def method(v, name, *args):
        return e.call(e.fld(e.v(v), name), args[0] if len(args) == 1 else e.tup(*args))

    def piece(name, *args):
        return e.p(name, method("w", name, *args) if args else method("w", name, e.tup()))

    return e.seq(
        e.let("p", e.call(_lo(e, "parser_type"), e.call(_lo(e, "parser_new"), null))),
        e.let("w", e.call(_lo(e, "writer_type"), e.call(_lo(e, "writer_new"), null))),
        e.mb.labeled(
            "doc",
            e.mb.loop(
                e.match_of(
                    method("p", "next", e.tup()),
                    "ev",
                    None,
                    e.p("end", e.mb.return_label("doc")),
                    e.p("error", on_error(e.v("ev"))),
                    piece("null"),
                    piece("bool", e.v("ev")),
                    piece("number", e.v("ev")),
                    piece("string", e.v("ev")),
                    piece("key", e.v("ev")),
                    piece("object_begin"),
                    piece("object_end"),
                    piece("array_begin"),
                    piece("array_end"),
                )
            ),
        ),
        e.call(_stdio(e, "write"), e.tup(null, e.n(ord("\n")))),
    )


def _error_report(e, null, code):
    """`json error <code>` on its own line, through a fresh writer for the digits."""
    return e.seq(
        *[e.call(_stdio(e, "write"), e.tup(null, e.n(ord(ch)))) for ch in ERROR_TEXT],
        e.seq(
            e.let("w2", e.call(_lo(e, "writer_type"), e.call(_lo(e, "writer_new"), null))),
            e.call(e.fld(e.v("w2"), "int"), code),
        ),
        e.call(_stdio(e, "write"), e.tup(null, e.n(ord("\n")))),
    )


def _llvm(e, mode):
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
    setup.append(
        e.let(
            "main_fn_t",
            e.call(
                e.fld(e.v("llvm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.fld(e.v("llvm"), "i32"))),
            ),
        )
    )
    setup.append(e.ret(e.rec(e.p("ll", e.v("ll")), e.p("main_fn_t", e.v("main_fn_t")))))

    top = []
    top.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    top.append(e.let("ll", e.fld(e.v("k"), "ll")))
    _json_lets(e, top, LLVM)
    null = _stdio(e, "null")

    def on_error(code):
        return e.seq(_error_report(e, null, code), e.call(_stdio(e, "exit"), e.n(1)))

    body = e.seq(_echo(e, null, on_error), e.ret(e.n(0)))
    top.append(
        e.let(
            "main",
            e.call(
                e.fld(e.v("llvm"), "func_fn"),
                e.rec(
                    e.p("mod", e.v("ll")),
                    e.p("name", e.s("main")),
                    e.p("params", e.tup()),
                    e.p("ty", e.fld(e.v("k"), "main_fn_t")),
                    e.p("body", e.stage(body)),
                ),
            ),
        )
    )
    top.append(root_mode_finish(mode, e, e.v("llvm"), e.v("ll")))
    return top


def _wasm(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(
        e.let(
            "start_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_void"))),
            ),
        )
    )
    setup.append(e.ret(e.rec(e.p("m", e.v("m")), e.p("start_fn_t", e.v("start_fn_t")))))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    top.append(e.let("m", e.fld(e.v("k"), "m")))
    _json_lets(e, top, WASM)
    null = e.mb.as_(e.n(0), _stdio(e, "pv"))

    def on_error(code):
        return e.seq(
            _error_report(e, null, code),
            e.call(_stdio(e, "flush"), e.tup()),
            e.call(_stdio(e, "exit"), e.n(1)),
        )

    body = e.seq(_echo(e, null, on_error), e.call(_stdio(e, "flush"), e.tup()))
    top.append(
        e.let(
            "start",
            e.call(
                e.fld(e.v("wasm"), "func_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("_start")),
                    e.p("params", e.tup()),
                    e.p("ty", e.fld(e.v("k"), "start_fn_t")),
                    e.p("body", e.stage(body)),
                ),
            ),
        )
    )
    top.append(e.call_m(e.v("m"), "export", e.s("_start")))
    top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    return top


def module(e, kind, mode=APP):
    if kind == WASM:
        return _wasm(e)
    if kind == LLVM:
        return _llvm(e, mode)
    raise AssertionError(kind)
