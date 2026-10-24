"""editor-hello-test.atz: the smallest editor on merman's editor protocol (harness/verify-editor-hello.sh): `_start`
puts a paragraph into the pane's element and opens the document `hello.txt`; an empty document is edited to
`edited` (an undo level), whose text the paragraph shows and which is written to `out.txt`; undo and redo of that
level swap the two texts; `stop` shows `stopped` and releases the handles."""

from .merman_editor import FILE as EDITOR_FILE
from ..editor import editor_types
from ..wasm.kit import Kit
from ..target_mb import fn_of

EDITED = "edited"


def module(e):
    k = Kit(e)
    setup = []
    k.bind(setup)
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    setup.append(e.let("editor", e.import_local("editor", EDITOR_FILE)))
    types = {
        "void_t": ([], "t_void"),
        "alloc_t": (["t_i32"], "t_i32"),
        "ret_i32_t": ([], "t_i32"),
        "doc_t": (["t_i32", "t_i32"], "t_void"),
        "level_t": (["t_i32", "t_i32", "t_i32"], "t_void"),
        "fs_t": (["t_i32", "t_i32", "t_i32", "t_i32"], "t_void"),
    }
    for name, (params, ret) in types.items():
        setup.append(e.let(name, k.fn_t(params, ret)))
    # `_start` takes the pane's element owned.
    setup.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    setup.append(e.let("root_h", e.call(e.fld(e.v("webidl"), "handle"), e.s("HTMLElement"))))
    setup.append(
        e.let(
            "start_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(
                    e.p("params", e.list_new(e.mb.eval_type(), e.fld(e.v("root_h"), "type"))),
                    e.p("ret", e.v("t_void")),
                ),
            ),
        )
    )
    host = ["doc_open", "doc_edit", "fs_write", "log"]
    for name in host:
        setup.append(e.let(name + "_t", e.call_m(e.fld(e.v("editor"), "fn_types"), "get", e.s(name))))
    exported = ["m", "t_i32", "t_pu8", "root_h", "start_t"] + list(types) + [n + "_t" for n in host]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("editor", e.import_local("editor", EDITOR_FILE)))
    top.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    top.append(e.let("heap", e.import_local("wasm_alloc", "wasm-alloc.atz")))
    top.append(e.let("ui", e.import_local("ui", "editor-ui.atz")))
    top.append(e.let("types", e.import_local("types", editor_types.FILE)))
    top.append(e.let("str_of", e.fld(e.v("types"), "str_of")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    for name in host:
        top.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "import_fn"),
                    e.rec(
                        e.p("module", e.fld(e.v("editor"), "module")),
                        e.p("name", e.s(name)),
                        e.p("ty", e.v(name + "_t")),
                    ),
                ),
            )
        )
    for name, text in [
        ("s_p", "p"),
        ("s_hello", "hello"),
        ("s_doc", "hello.txt"),
        ("s_key", "1"),
        ("s_edited", EDITED),
        ("s_level", "L"),
        ("s_out", "out.txt"),
        ("s_fs", "fs done"),
        ("s_stopped", "stopped"),
    ]:
        top.append(e.let(name, e.call_m(e.v("m"), "cstr", e.s(text))))
    # cells: the root, the paragraph, the document's pointer and length
    top.append(
        e.let(
            "cells",
            e.call(
                e.fld(e.v("wasm"), "data_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("cells")),
                    e.p("elem", e.v("t_i32")),
                    e.p("values", e.tup(e.n(0), e.n(0), e.n(0), e.n(0))),
                ),
            ),
        )
    )

    def hook(kind, iface, member):
        return e.call(e.fld(e.v("webidl"), kind), e.rec(e.p("iface", e.s(iface)), e.p("member", e.s(member))))

    for bind, kind, iface, member in [
        ("h_owner", "get", "Node", "ownerDocument"),
        ("h_create", "op", "Document", "createElement"),
        ("h_append", "op", "Node", "appendChild"),
        ("h_text", "set", "Node", "textContent"),
    ]:
        top.append(e.let(bind, hook(kind, iface, member)))
    for name, iface in [("p_h", "HTMLElement")]:
        top.append(e.let(name, e.call(e.fld(e.v("webidl"), "handle"), e.s(iface))))

    def cell(i):
        return e.mb.field(k.lo("cells"), e.n(i))

    def length(text):
        return e.n(len(text.encode()))

    def show(addr, len_):
        """Sets the paragraph's text to the `len_` bytes at the address `addr` (editor-ui's `text` over the paragraph's
        handle as a raw `Element` and the bytes as a `str`)."""
        return k.lib(
            "ui",
            "text",
            e.mb.as_(cell(1), e.lower(e.fld(e.v("ui"), "el_raw"))),
            k.str_of(k.ptr_of(addr, "t_pu8"), len_),
        )

    def doc_bytes():
        return k.ptr_of(cell(2), "t_pu8")

    start = e.seq(
        e.let("root", e.call(e.fld(e.v("r"), "move"), e.tup())),
        # the root's document (nullable in the spec: an attached element has one; none traps)
        e.match_of(
            k.call("h_owner", e.v("root")),
            "doc",
            None,
            e.p("none", e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())),
            e.p(
                "some",
                e.seq(
                    e.let("para", k.call("h_create", e.v("doc"), k.lo("s_p"), e.n(1), e.n(0), e.n(0), e.n(0))),
                    k.call("h_text", e.v("para"), e.n(1), k.lo("s_hello"), length("hello")),
                    k.call("h_append", e.v("root"), e.v("para")),
                    e.mb.set(cell(1), e.call(e.fld(e.v("para"), "forget"), e.tup())),
                ),
            ),
        ),
        e.mb.set(cell(0), e.call(e.fld(e.v("root"), "forget"), e.tup())),
        k.call("doc_open", k.lo("s_doc"), length("hello.txt"), k.lo("s_key"), e.n(1)),
    )
    edited = k.addr(k.lo("s_edited"))
    on_doc = e.seq(
        e.mb.set(cell(2), e.v("ptr")),
        e.mb.set(cell(3), e.v("len")),
        e.if_only(
            e.eq(e.v("len"), e.n(0)),
            e.seq(
                e.mb.set(cell(2), edited),
                e.mb.set(cell(3), length(EDITED)),
                k.call("doc_edit", k.lo("s_level"), e.n(1)),
            ),
        ),
        show(cell(2), cell(3)),
        k.call("fs_write", e.n(7), k.lo("s_out"), length("out.txt"), doc_bytes(), cell(3)),
    )
    on_level = e.seq(
        e.mb.set(cell(2), edited),
        e.mb.set(cell(3), e.if_else(e.eq(e.v("redo"), e.n(0)), k.i32(0), k.i32(len(EDITED.encode())))),
        show(cell(2), cell(3)),
    )
    stop = e.seq(
        show(k.addr(k.lo("s_stopped")), length("stopped")),
        # Adopted back, the handles are released when these bindings drop.
        e.let("para", e.mb.as_(cell(1), e.lower(e.fld(e.v("p_h"), "own")))),
        e.let("root", e.mb.as_(cell(0), e.lower(e.fld(e.v("root_h"), "own")))),
    )
    exports = [
        ("_start", e.tup(e.s("r")), "start_t", start),
        ("stop", e.tup(), "void_t", stop),
        ("alloc", e.tup(e.s("n")), "alloc_t", e.ret(k.addr(e.call(e.lower(e.fld(e.v("heap"), "malloc")), e.v("n"))))),
        ("doc_ptr", e.tup(), "ret_i32_t", e.ret(cell(2))),
        ("doc_len", e.tup(), "ret_i32_t", e.ret(cell(3))),
        ("on_doc", e.tup(e.s("ptr"), e.s("len")), "doc_t", on_doc),
        ("on_level", e.tup(e.s("ptr"), e.s("len"), e.s("redo")), "level_t", on_level),
        (
            "on_fs",
            e.tup(e.s("req"), e.s("status"), e.s("ptr"), e.s("len")),
            "fs_t",
            k.call("log", k.lo("s_fs"), length("fs done")),
        ),
    ]
    for name, params, ty_, body_ in exports:
        top.append(
            e.call(
                e.fld(e.v("wasm"), "export_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s(name)),
                    e.p("params", params),
                    e.p("ty", e.v(ty_)),
                    e.p("body", e.stage(e.seq(body_))),
                ),
            )
        )
    top.append(e.ret(e.call(e.fld(e.v("editor"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
