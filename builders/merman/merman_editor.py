"""merman-editor.atz: the `editor` marker merman opens as a pane, and the typed imports of merman's host.

A module whose root export is an `editor` instance shows an editor button in merman. The editor's `files` hold an
ES module `main.js` and the wasm `main.wasm` (and their debug maps), made by `build` from a wat module (web-wasm.atz's
`module_build`, so the wasm reaches the DOM through webidl-wasm.atz's hooks). The pane imports `main.js` and starts
it with an element: the wasm's `_start(root)` gets an owned handle of that element and builds the editor inside it;
before the pane loads a new build, and when it closes, it calls the wasm's `stop()`, after which the editor must
have released everything it holds outside `root` (listeners on other targets, animation frames, timers).

The imports below come from the module `merman` (pointers are byte offsets into the module's exported memory):
`fs_read(req, path)` and `fs_write(req, path, bytes)` take a path relative to the directory of the module that
exported the editor (the editor's working directory, where its documents are too) and answer with
`on_fs(req, status, ptr, len)` (status 0 ok, 1 failed, 2 no memory), the host writing file bytes at what
`alloc(len) -> ptr` returns first; `log(text)` writes to the console. File requests complete by callback because
every server round trip in the browser is asynchronous.

A document is a file the editor serializes itself, kept in the ide's undo history. `doc_open(name, key)` opens the
file named `name` next to the module that exported the editor, under an undo tag made of that module and `key`
(the editor's format version), and the contents arrive by `on_doc(ptr, len)`. The editor exposes the document
through `doc_ptr() -> ptr` and `doc_len() -> len`; after `doc_edit(level)`, where `level` is whatever the editor
needs to undo or redo that change, the host records the level and reads the new contents from there. Undo and redo
hand a level back through `on_level(ptr, len, redo)`, after which the host reads the contents again. A change to
the file from outside arrives as another `on_doc`.
"""

from ..wasm.wat import bind_types

FILE = "merman-editor.atz"

MODULE = "merman"

# (name, parameter wasm types, result wasm type)
IMPORTS = [
    ("fs_read", ["i32", "pu8", "i32"], "void"),
    ("fs_write", ["i32", "pu8", "i32", "pu8", "i32"], "void"),
    ("log", ["pu8", "i32"], "void"),
    ("doc_open", ["pu8", "i32", "pu8", "i32"], "void"),
    ("doc_edit", ["pu8", "i32"], "void"),
]


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
    top.append(e.let("web", e.import_local("web", "web-wasm.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    top.append(e.let("d", e.define()))
    top.append(e.option_type_let())
    top.append(e.let("editor_o", e.def_object(e.v("d"), "editor")))
    top.append(e.object_impl(e.v("editor_o"), e.rec(e.p("files", e.mb.builtin("types", "dir")))))
    top.append(e.let("build_b", e.def_func(e.v("d"), "build")))
    body = []
    body.append(
        e.let(
            "files",
            e.call(
                e.lower(e.fld(e.v("web"), "module_build")),
                e.rec(
                    e.p("wat", e.fld(e.v("arg"), "wat")),
                    e.p("meta", e.fld(e.v("arg"), "meta")),
                    e.p("frames", e.fld(e.v("arg"), "frames")),
                    e.p("host_module", e.s(MODULE)),
                ),
            ),
        )
    )
    body.append(e.ret(e.call(e.lower(e.fld(e.v("editor_o"), "new")), e.rec(e.p("files", e.v("files"))))))
    top.append(
        e.func_impl(
            e.v("build_b"),
            e.rec(
                e.p("wat", e.mb.types_string()),
                e.p("meta", e.list_type(e.fld(e.v("wasm"), "meta_t"))),
                e.p("frames", e.mb.types_string()),
            ),
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
