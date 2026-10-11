"""merman-editor.atz: the `editor` marker merman opens as a pane, and the typed imports of merman's host.

A module whose root export is an `editor` instance shows an editor button in merman; the pane instantiates
the wasm in `files` (`main.wasm`) with the imports below under the module name `merman` (pointers
are byte offsets into the module's exported memory; `canvas_segment` takes two points, a width and
a color as 0xRRGGBBAA; `button_add` and `text_set` take utf-8; `fs_read` and `fs_write` take a path
relative to the editor's directory and answer with `on_fs`), then calls the exports it finds: `_start()`, `on_pointer(kind, x, y, pressure, tilt_x, tilt_y, t_ms)` (kind 0
down, 1 move, 2 up), `on_button(id)`, `on_key(code, mods) -> handled`, `on_fs(req, status, ptr, len)`
and `alloc(len) -> ptr` (the host writes file bytes there before `on_fs`). File requests complete by
callback because every server round trip in the browser is asynchronous.

A document is a file the extension serializes itself, kept in the ide's undo history. `doc_open(name,
key)` opens the file named `name` next to the module that exported the editor, under an undo tag made
of that module and `key` (the extension's format version), and the contents arrive by `on_doc(ptr,
len)`. The extension exposes the document through `doc_ptr() -> ptr` and `doc_len() -> len`; after
`doc_edit(level)`, where `level` is whatever the extension needs to undo or redo that change, the host
records the level and reads the new contents from there. Undo and redo hand a level back through
`on_level(ptr, len, redo)`, after which the host reads the contents again. A change to the file from
outside arrives as another `on_doc`.
"""

from .wat import bind_types

FILE = "merman-editor.atz"

MODULE = "merman"

# (name, parameter wasm types, result wasm type)
IMPORTS = [
    ("canvas_clear", [], "void"),
    ("canvas_segment", ["f64", "f64", "f64", "f64", "f64", "u32"], "void"),
    ("canvas_polyline", ["pf64", "i32", "f64", "u32"], "void"),
    ("button_add", ["pu8", "i32"], "i32"),
    ("text_set", ["pu8", "i32"], "void"),
    ("fs_read", ["i32", "pu8", "i32"], "void"),
    ("fs_write", ["i32", "pu8", "i32", "pu8", "i32"], "void"),
    ("now_ms", [], "f64"),
    ("log", ["pu8", "i32"], "void"),
    ("doc_open", ["pu8", "i32", "pu8", "i32"], "void"),
    ("doc_edit", ["pu8", "i32"], "void"),
]

WASM = "main.wasm"


def _bytes_t(e):
    return e.call(e.mb.types_array(), e.mb.types_byte())


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    bind_types(e, setup)
    setup.append(e.let("t_pf64", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_f64"))))
    entries = []
    for name, params, ret in IMPORTS:
        param_types = []
        for param in params:
            param_types.append(e.v("t_" + param))
        entries.append(
            e.p(
                name,
                e.call(
                    e.fld(e.v("wasm"), "fn"),
                    e.rec(
                        e.p("params", e.list_new(e.mb.eval_type(), *param_types)),
                        e.p("ret", e.v("t_" + ret)),
                    ),
                ),
            )
        )
    setup.append(e.ret(e.rec(e.p("fn_types", e.map_new(e.mb.types_string(), e.mb.eval_type(), *entries)))))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    top.append(e.let("d", e.define()))
    top.append(e.option_type_let())
    top.append(e.let("editor_o", e.def_object(e.v("d"), "editor")))
    top.append(e.object_impl(e.v("editor_o"), e.rec(e.p("files", e.mb.builtin("types", "dir")))))
    top.append(e.let("build_b", e.def_func(e.v("d"), "build")))
    body = []
    body.append(
        e.let(
            "r",
            e.call(
                e.mb.builtin("exec"),
                e.rec(
                    e.p("command", e.s("wat2wasm")),
                    e.p("args", e.str_list(e.s("main.wat"), e.s("-o"), e.s(WASM))),
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
    body.append(e.let("f", e.call_m(e.call_m0(e.v("r"), "dir"), "open", e.s(WASM))))
    body.append(
        e.let(
            "wasm_bytes",
            e.call_m(e.v("f"), "read", e.rec(e.p("offset", e.int_of(0)), e.p("len", e.fld(e.v("f"), "len")))),
        )
    )
    body.append(
        e.ret(
            e.call(
                e.lower(e.fld(e.v("editor_o"), "new")),
                e.rec(
                    e.p(
                        "files",
                        e.call(
                            e.mb.builtin("dir"),
                            e.map_new(e.mb.types_string(), _bytes_t(e), e.p(WASM, e.v("wasm_bytes"))),
                        ),
                    )
                ),
            )
        )
    )
    top.append(
        e.func_impl(
            e.v("build_b"),
            e.rec(e.p("wat", e.mb.types_string()), e.p("meta", e.list_type(e.fld(e.v("wasm"), "meta_t")))),
            e.option_type_some(e.fld(e.v("editor_o"), "type")),
            e.mb.opt_none_type(),
            e.stage(e.mb.seq(body)),
        )
    )
    top.append(e.finish(e.v("d")))
    top.append(
        e.ret(
            e.rec(
                e.p("module", e.s(MODULE)),
                e.p("fn_types", e.fld(e.v("k"), "fn_types")),
                e.p("editor_t", e.fld(e.v("editor_o"), "type")),
                e.p("build", e.fld(e.v("build_b"), "func")),
            )
        )
    )
    return top
