"""web-wasm.atz: `build` packages a wat module as a browser app dir: index.html, main.js, main.wasm, and their debug
maps (main.js.map over main.js.frames.json, main.wasm.map over frames.json, the wat module's frames).
`module_build` packages it as an ES module instead (no index.html): main.js exports `start({root, host, wasm})`,
which gives the imports of the wasm module's `host_module` from `host.imports`, instantiates the wasm at the URL
`wasm`, calls `host.attach(instance)` and then `_start(root)` with an owned handle of the element `root`."""

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


def _jsc(e, kind, *fields):
    """A call of the js definition const function `kind` (from a staged body)."""
    return e.call(e.lower(e.fld(e.v("js"), kind)), e.rec(*fields))


def _jfn(e, params, ret):
    return _jsc(e, "fn", e.p("params", e.tup(*params)), e.p("ret", ret))


def _declare(e, body):
    """The browser API the loader uses, declared."""
    # The browser API the loader uses, declared: `fetch`, `WebAssembly.instantiateStreaming` and what its promise
    # yields (the instance and its `_start` export), and the module variables `imports` and `instance`.
    objects = [
        ("response_p", "Promise<Response>"),
        ("exports_t", "WebAssembly.Exports"),
        ("instance_t", "WebAssembly.Instance"),
        ("source_t", "WebAssembly.WebAssemblyInstantiatedSource"),
        ("done_p", "Promise<undefined>"),
        ("source_p", "Promise<WebAssembly.WebAssemblyInstantiatedSource>"),
        ("webidl_t", "Imports.webidl"),
        ("imports_t", "Imports"),
    ]
    for name, js_name in objects:
        body.append(e.let(name, _jsc(e, "object", e.p("name", e.s(js_name)))))
    string = e.lower(e.fld(e.v("js"), "string"))
    void = e.lower(e.fld(e.v("js"), "void"))
    for obj, fields, methods in [
        ("exports_t", [], [("_start", _jfn(e, [], void))]),
        ("instance_t", [("exports", e.v("exports_t"))], []),
        ("source_t", [("instance", e.v("instance_t"))], []),
        ("source_p", [], [("then", _jfn(e, [_jfn(e, [e.v("source_t")], void)], e.v("done_p")))]),
        ("imports_t", [("webidl", e.v("webidl_t"))], []),
    ]:
        body.append(
            _jsc(
                e,
                "members",
                e.p("object", e.v(obj)),
                e.p("fields", e.rec(*[e.p(k, v) for k, v in fields])),
                e.p("methods", e.rec(*[e.p(k, v) for k, v in methods])),
            )
        )
    for g, js_name, ty_ in [
        (
            "WebAssembly_instantiate",
            "WebAssembly.instantiateStreaming",
            _jfn(e, [e.v("response_p"), e.v("imports_t")], e.v("source_p")),
        ),
        ("fetch", "fetch", _jfn(e, [string], e.v("response_p"))),
        ("instance", "instance", e.v("instance_t")),
    ]:
        body.append(e.let(g, _jsc(e, "global_fn", e.p("name", e.s(js_name)), e.p("ty", ty_))))


def _assemble(e, body):
    """Assembles the wat text (`arg.wat`) into `wasm_bytes` and its map `wasm_map`."""
    body.append(
        e.let(
            "r",
            e.call(
                e.mb.builtin("exec"),
                e.rec(
                    # binaryen's assembler: it turns the text's `;;@` annotations into the source map. The features
                    # are the ones the wat target emits (`-all` would also enable proposals browsers reject).
                    e.p("command", e.s("wasm-as")),
                    e.p(
                        "args",
                        e.str_list(
                            e.s("main.wat"),
                            e.s("--enable-bulk-memory"),
                            e.s("--enable-multivalue"),
                            e.s("--enable-sign-ext"),
                            e.s("--enable-mutable-globals"),
                            e.s("--enable-nontrapping-float-to-int"),
                            e.s("-o"),
                            e.s("main.wasm"),
                            e.s("--source-map"),
                            e.s("main.wasm.map"),
                            e.s("--source-map-url"),
                            e.s("main.wasm.map"),
                        ),
                    ),
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
    for var, name in [("wasm_bytes", "main.wasm"), ("wasm_map", "main.wasm.map")]:
        body.append(e.let(var + "_f", e.call_m(e.call_m0(e.v("r"), "dir"), "open", e.s(name))))
        body.append(
            e.let(
                var,
                e.call_m(
                    e.v(var + "_f"),
                    "read",
                    e.rec(e.p("offset", e.int_of(0)), e.p("len", e.fld(e.v(var + "_f"), "len"))),
                ),
            )
        )


def _glue(e, body):
    """The js module `m` with the webidl runtime `rt` and the module variable `imports`, holding the glue of every
    `webidl` import the wasm module's meta names."""
    body.append(e.let("m", e.call(e.lower(e.fld(e.v("js"), "new")), e.tup())))
    body.append(e.let("rt", e.call(e.lower(e.fld(e.v("webidl"), "runtime")), e.rec(e.p("mod", e.v("m"))))))
    body.append(
        e.let(
            "imports",
            _jsc(e, "var_fn", e.p("mod", e.v("m")), e.p("name", e.s("imports")), e.p("ty", e.v("imports_t"))),
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


def _dir(e, html):
    """The output dir: the js module (`out`, rendered), the wasm module and their maps, and `index.html` when `html`."""
    entries = []
    if html:
        entries.append(e.p("index.html", e.call(e.mb.eval_str_utf8(), e.s(HTML))))
    entries += [
        e.p(
            "main.js",
            e.call(e.mb.eval_str_utf8(), e.cat(e.fld(e.v("out"), "js"), e.s("//# sourceMappingURL=main.js.map\n"))),
        ),
        e.p("main.js.map", e.call(e.mb.eval_str_utf8(), e.fld(e.v("out"), "map"))),
        e.p("main.js.frames.json", e.call(e.mb.eval_str_utf8(), e.fld(e.v("out"), "frames"))),
        e.p("main.wasm", e.v("wasm_bytes")),
        e.p("main.wasm.map", e.v("wasm_map")),
        e.p("frames.json", e.call(e.mb.eval_str_utf8(), e.fld(e.v("arg"), "frames"))),
    ]
    return e.call(e.mb.builtin("dir"), e.map_new(e.mb.types_string(), _bytes_t(e), *entries))


# The ES module's `start({root, host, wasm})`: `host.imports` become the imports of the module `host_module` (an
# identifier), the wasm at the URL `wasm` is instantiated, `host.attach(instance)` runs, then `_start` with an owned
# handle of `root`. Its promise settles once `_start` returns.
START_LINES = [
    ["imports.", "$host_module", " = opts.host.imports;"],
    ["return WebAssembly.instantiateStreaming(fetch(opts.wasm), imports).then(function (r) {"],
    ["  instance = r.instance;"],
    ["  opts.host.attach(instance);"],
    ["  instance.exports._start(", "$h_new", "(opts.root));"],
    ["});"],
]


def _start_line(e, parts):
    out = []
    for part in parts:
        if part == "$host_module":
            out.append(e.fld(e.v("arg"), "host_module"))
        elif part == "$h_new":
            out.append(e.fld(e.v("rt"), "h_new"))
        else:
            out.append(e.s(part))
    return e.cat(*out)


def module(e):
    top = []
    top.append(e.let("js", e.import_local("js", "js-es2020.atz")))
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("webidl", e.import_local("webidl", "webidl-js.atz")))
    top.append(e.let("d", e.define()))
    top.append(e.option_type_let())
    top.append(e.let("build_b", e.def_func(e.v("d"), "build")))
    body = []
    _declare(e, body)
    _assemble(e, body)
    _glue(e, body)
    void = e.lower(e.fld(e.v("js"), "void"))
    body.append(
        e.let(
            "ready",
            e.call(
                e.lower(e.fld(e.v("js"), "func_fn")),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("ready")),
                    e.p("params", e.tup(e.s("r"))),
                    e.p("ty", _jfn(e, [e.v("source_t")], void)),
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
                            e.lower(e.v("WebAssembly_instantiate")),
                            e.tup(e.call(e.lower(e.v("fetch")), e.s("main.wasm")), e.lower(e.v("imports"))),
                        ),
                        "then",
                    ),
                    e.lower(e.v("ready")),
                )
            ),
        )
    )
    body.append(e.let("out", e.call_m(e.v("m"), "render", e.rec(e.p("frames", e.s("main.js.frames.json"))))))
    body.append(e.ret(_dir(e, True)))
    top.append(
        e.func_impl(
            e.v("build_b"),
            e.rec(
                e.p("wat", e.mb.types_string()),
                e.p("meta", e.list_type(e.fld(e.v("wasm"), "meta_t"))),
                e.p("frames", e.mb.types_string()),
            ),
            e.option_type_some(e.mb.builtin("types", "dir")),
            e.mb.opt_none_type(),
            e.stage(e.mb.seq(body)),
        )
    )
    top.append(e.let("module_build_b", e.def_func(e.v("d"), "module_build")))
    mbody = []
    _declare(e, mbody)
    _assemble(e, mbody)
    _glue(e, mbody)
    mbody.append(
        e.let(
            "start",
            e.call_m(
                e.v("m"),
                "func_text",
                e.rec(
                    e.p("name", e.s("start")),
                    e.p("params", e.str_list(e.s("opts"))),
                    e.p("lines", e.list_new(e.mb.types_string(), *[_start_line(e, line) for line in START_LINES])),
                ),
            ),
        )
    )
    mbody.append(e.call_m(e.v("m"), "export", e.rec(e.p("name", e.v("start")), e.p("as", e.s("start")))))
    mbody.append(e.let("out", e.call_m(e.v("m"), "render", e.rec(e.p("frames", e.s("main.js.frames.json"))))))
    mbody.append(e.ret(_dir(e, False)))
    top.append(
        e.func_impl(
            e.v("module_build_b"),
            e.rec(
                e.p("wat", e.mb.types_string()),
                e.p("meta", e.list_type(e.fld(e.v("wasm"), "meta_t"))),
                e.p("frames", e.mb.types_string()),
                e.p("host_module", e.mb.types_string()),
            ),
            e.option_type_some(e.mb.builtin("types", "dir")),
            e.mb.opt_none_type(),
            e.stage(e.mb.seq(mbody)),
        )
    )
    top.append(e.finish(e.v("d")))
    top.append(
        e.ret(
            e.rec(
                e.p("build", e.fld(e.v("build_b"), "func")), e.p("module_build", e.fld(e.v("module_build_b"), "func"))
            )
        )
    )
    return top
