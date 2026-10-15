"""web-wasm.atz: `build` helper packaging a wat module as a browser app dir (index.html, main.js, main.wasm)."""

from . import webidl_wasm
from ..target_mb import p_

HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"></head>
<body><script src="main.js"></script></body>
</html>
"""


def _bytes_t(e):
    return e.call(e.mb.types_array(), e.mb.types_byte())


def module(e):
    top = []
    top.append(e.let("js", e.import_local("js", "js-es2020.atz")))
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("webidl", e.import_local("webidl", "webidl-js.atz")))
    top.append(e.let("d", e.define()))
    top.append(e.option_type_let())
    top.append(e.let("build_b", e.def_func(e.v("d"), "build")))
    body = []
    for g in ["WebAssembly", "fetch", "instance"]:
        body.append(e.let(g, e.call(e.lower(e.fld(e.v("js"), "global_fn")), e.rec(e.p("name", e.s(g))))))
    body.append(
        e.let(
            "r",
            e.call(
                e.mb.builtin("exec"),
                e.rec(
                    e.p("command", e.s("wat2wasm")),
                    e.p("args", e.str_list(e.s("main.wat"), e.s("-o"), e.s("main.wasm"))),
                    e.p("env", e.map_new(e.mb.types_string(), e.mb.types_string())),
                    e.p(
                        "files",
                        e.map_new(
                            e.mb.types_string(),
                            _bytes_t(e),
                            e.p("main.wat", e.call(e.mb.eval_str_utf8(), e.fld(e.v("arg"), "wat"))),
                        ),
                    ),
                    e.p("success_codes", e.opt_none(e.list_type(e.mb.types_int()))),
                ),
            ),
        )
    )
    body.append(e.let("f", e.call_m(e.call_m0(e.v("r"), "dir"), "open", e.s("main.wasm"))))
    body.append(
        e.let(
            "wasm_bytes",
            e.call_m(e.v("f"), "read", e.rec(e.p("offset", e.int_of(0)), e.p("len", e.fld(e.v("f"), "len")))),
        )
    )
    body.append(e.let("m", e.call(e.lower(e.fld(e.v("js"), "new")), e.tup())))
    body.append(e.let("rt", e.call(e.lower(e.fld(e.v("webidl"), "runtime")), e.rec(e.p("mod", e.v("m"))))))
    body.append(
        e.let(
            "imports",
            e.call(e.lower(e.fld(e.v("js"), "var_fn")), e.rec(e.p("mod", e.v("m")), e.p("name", e.s("imports")))),
        )
    )
    body.append(e.call_m(e.v("m"), "run", e.stage(e.mb.set(e.lower(e.v("imports")), e.rec(e.p("webidl", e.rec()))))))
    define = e.call(
        e.lower(e.fld(e.v("webidl"), "define")),
        e.rec(e.p("mod", e.v("m")), e.p("name", p_(e, "name")), e.p("rt", e.v("rt"))),
    )
    assign = e.call_m(
        e.v("m"),
        "assign_index",
        e.rec(e.p("target", e.s("imports.webidl")), e.p("key", p_(e, "name")), e.p("value", define)),
    )
    on_import = e.if_only(e.eq(p_(e, "module"), e.s(webidl_wasm.MODULE)), assign)
    on_dep = e.match_of(e.call_m0(e.fld(e.v("mk"), "dep"), "k"), "p", None, e.p("import", on_import))
    body.append(
        e.foreach(
            e.fld(e.v("arg"), "meta"),
            "m0",
            e.match_of(e.call_m0(e.v("m0"), "k"), "mk", None, e.p("dep", on_dep), e.p("other", e.seq())),
        )
    )
    body.append(
        e.let(
            "ready",
            e.call(
                e.lower(e.fld(e.v("js"), "func_fn")),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("ready")),
                    e.p("params", e.tup(e.s("r"))),
                    e.p(
                        "body",
                        e.stage(
                            e.seq(
                                e.mb.set(e.lower(e.v("instance")), e.fld(e.v("r"), "instance")),
                                e.call(e.fld(e.lower(e.v("instance")), "exports", "_start"), e.tup()),
                            )
                        ),
                    ),
                ),
            ),
        )
    )
    body.append(
        e.call_m(
            e.v("m"),
            "run",
            e.stage(
                e.call(
                    e.fld(
                        e.call(
                            e.fld(e.lower(e.v("WebAssembly")), "instantiateStreaming"),
                            e.tup(e.call(e.lower(e.v("fetch")), e.s("main.wasm")), e.lower(e.v("imports"))),
                        ),
                        "then",
                    ),
                    e.lower(e.v("ready")),
                )
            ),
        )
    )
    body.append(e.let("out", e.call_m0(e.v("m"), "render")))
    body.append(
        e.ret(
            e.call(
                e.mb.builtin("dir"),
                e.map_new(
                    e.mb.types_string(),
                    _bytes_t(e),
                    e.p("index.html", e.call(e.mb.eval_str_utf8(), e.s(HTML))),
                    e.p("main.js", e.call(e.mb.eval_str_utf8(), e.fld(e.v("out"), "js"))),
                    e.p("main.wasm", e.v("wasm_bytes")),
                ),
            )
        )
    )
    top.append(
        e.func_impl(
            e.v("build_b"),
            e.rec(e.p("wat", e.mb.types_string()), e.p("meta", e.list_type(e.fld(e.v("wasm"), "meta_t")))),
            e.option_type_some(e.mb.builtin("types", "dir")),
            e.mb.opt_none_type(),
            e.stage(e.mb.seq(body)),
        )
    )
    top.append(e.finish(e.v("d")))
    top.append(e.ret(e.rec(e.p("build", e.fld(e.v("build_b"), "func")))))
    return top
