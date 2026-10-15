"""stylus-recorder.atz: a merman editor pane recording stylus samples and drawing the strokes.

Every pointer sample (time since the first sample, kind, position, pressure, tilt) is a row of the
document, a file of such rows next to this module that the pane keeps in the ide's undo history:
each stroke and each clear is one undo level holding the rows it added or removed. While the stylus
is down each move draws a segment whose width follows the pressure, and the strokes are redrawn
whenever the document is loaded or a level is applied.
"""

from .merman_editor import FILE as EDITOR_FILE
from ..wasm.wat import bind_types

FIELDS = 7
ROW = FIELDS * 8
LEVEL_HEADER = 16
PAGE = 65536
COLOR = 0xE0C060FF
CLEAR = "Clear"
DOC = "stylus-recorder.bin"
DOC_KEY = "1"
HOST = ["canvas_clear", "canvas_segment", "button_add", "doc_open", "doc_edit"]
EXPORTS = [
    "_start",
    "on_pointer",
    "on_button",
    "alloc",
    "doc_ptr",
    "doc_len",
    "on_doc",
    "on_level",
]

# cells: row count, stylus down, the clear button's id, the document's rows, their capacity in
# rows, the end of what the bump allocator handed out, the row the current stroke began at
CELL_COUNT = 0
CELL_DOWN = 1
CELL_CLEAR = 2
CELL_BUF = 3
CELL_CAP = 4
CELL_HEAP = 5
CELL_START = 6
# floats: previous x, previous y, the first sample's time
FLOAT_PREV_X = 0
FLOAT_PREV_Y = 1
FLOAT_T0 = 2
# row fields
ROW_T = 0
ROW_KIND = 1
ROW_X = 2
ROW_Y = 3
ROW_P = 4


def _cell(e, index):
    return e.mb.field(e.lower(e.v("cells")), e.n(index))


def _float(e, index):
    return e.mb.field(e.mb.as_(e.lower(e.v("floats")), e.lower(e.v("t_pf64"))), e.n(index))


def _call(e, name, args):
    """A wasm function takes one argument bare and several as a tuple."""
    return e.call(e.lower(e.v(name)), args[0] if len(args) == 1 else e.tup(*args))


def _host(e, name, *args):
    return _call(e, name, args)


def _fn(e, name, *args):
    return _call(e, name, args)


def _f64p(e, addr):
    return e.mb.as_(addr, e.lower(e.v("t_pf64")))


def _i32(e, v):
    """An f64 value truncated to i32."""
    return e.call(e.fld(v, "trunc"), e.lower(e.v("t_i32")))


def _f64(e, v):
    return e.mb.as_(v, e.lower(e.v("t_f64")))


def _row_field(e, buf, row, field):
    return e.mb.field(_f64p(e, buf), e.mb.operator_add(e.mb.operator_mul(row, e.n(FIELDS)), e.n(field)))


def _fn_t(e, params, ret):
    param_types = []
    for param in params:
        param_types.append(e.v("t_" + param))
    return e.call(
        e.fld(e.v("wasm"), "fn"),
        e.rec(e.p("params", e.list_new(e.mb.eval_type(), *param_types)), e.p("ret", e.v("t_" + ret))),
    )


def _loop(e, label, body):
    return e.mb.labeled(label, e.foreach(e.lower(e.v("loop")), "_", body))


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("t_pf64", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_f64"))))
    fn_types = {
        "void_fn_t": ([], "void"),
        "pointer_fn_t": (["i32", "f64", "f64", "f64", "f64", "f64", "f64"], "void"),
        "i32_fn_t": (["i32"], "void"),
        "i32_i32_fn_t": (["i32"], "i32"),
        "ret_i32_fn_t": ([], "i32"),
        "i32_i32_void_fn_t": (["i32", "i32"], "void"),
        "i32_i32_i32_void_fn_t": (["i32", "i32", "i32"], "void"),
    }
    for name, (params, ret) in fn_types.items():
        setup.append(e.let(name, _fn_t(e, params, ret)))
    setup.append(e.let("editor", e.import_local("editor", EDITOR_FILE)))
    exported = ["m", "t_i32", "t_f64", "t_pf64", "t_pu8"] + list(fn_types)
    for name in HOST:
        setup.append(e.let(name + "_fn_t", e.call_m(e.fld(e.v("editor"), "fn_types"), "get", e.s(name))))
        exported.append(name + "_fn_t")
    exported_fields = []
    for n in exported:
        exported_fields.append(e.p(n, e.v(n)))
    setup.append(e.ret(e.rec(*exported_fields)))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("editor", e.import_local("editor", EDITOR_FILE)))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    for name in ["loop", "memory_grow", "memory_copy"]:
        top.append(e.let(name, e.call(e.fld(e.v("wasm"), name + "_fn"), e.rec())))
    for name in HOST:
        top.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "import_fn"),
                    e.rec(
                        e.p("module", e.fld(e.v("editor"), "module")),
                        e.p("name", e.s(name)),
                        e.p("ty", e.v(name + "_fn_t")),
                    ),
                ),
            )
        )
    zeros = []
    for _ in range(7):
        zeros.append(e.n(0))
    top.append(
        e.let(
            "cells",
            e.call(
                e.fld(e.v("wasm"), "data_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("cells")),
                    e.p("elem", e.v("t_i32")),
                    e.p("values", e.tup(*zeros)),
                ),
            ),
        )
    )
    for name, size in [("floats", 3 * 8), ("heap", 16)]:
        top.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "alloc_fn"),
                    e.rec(e.p("mod", e.v("m")), e.p("name", e.s(name)), e.p("size", e.n(size))),
                ),
            )
        )
    for name, text in [("clear_label", CLEAR), ("doc_name", DOC), ("doc_key", DOC_KEY)]:
        top.append(e.let(name, e.call_m(e.v("m"), "cstr", e.s(text))))

    # bump(size): the next `size` bytes past everything handed out so far, growing memory as
    # needed. Nothing is ever freed; the document moves to a fresh region when it outgrows one.
    bump_body = e.stage(
        e.seq(
            e.let("at", _cell(e, CELL_HEAP)),
            e.let("need", e.mb.operator_add(e.v("at"), e.v("size"))),
            e.let("have", e.mb.operator_mul(_fn(e, "memory_grow", e.n(0)), e.n(PAGE))),
            e.if_only(
                e.mb.operator_gt(e.v("need"), e.v("have")),
                e.seq(
                    e.let(
                        "grown",
                        _fn(
                            e,
                            "memory_grow",
                            e.mb.operator_div(
                                e.mb.operator_add(e.mb.operator_sub(e.v("need"), e.v("have")), e.n(PAGE - 1)),
                                e.n(PAGE),
                            ),
                        ),
                    )
                ),
            ),
            e.mb.set(
                _cell(e, CELL_HEAP),
                e.mb.operator_mul(e.mb.operator_div(e.mb.operator_add(e.v("need"), e.n(7)), e.n(8)), e.n(8)),
            ),
            e.ret(e.v("at")),
        )
    )
    # reserve(rows): room for that many more rows, moving the document if it has to grow.
    reserve_body = e.stage(
        e.seq(
            e.let("want", e.mb.operator_add(_cell(e, CELL_COUNT), e.v("rows"))),
            e.if_only(
                e.mb.operator_gt(e.v("want"), _cell(e, CELL_CAP)),
                e.seq(
                    e.let("cap", e.mb.operator_add(e.mb.operator_mul(e.v("want"), e.n(2)), e.n(16))),
                    e.let("moved", _fn(e, "bump", e.mb.operator_mul(e.v("cap"), e.n(ROW)))),
                    _fn(
                        e,
                        "memory_copy",
                        e.v("moved"),
                        _cell(e, CELL_BUF),
                        e.mb.operator_mul(_cell(e, CELL_COUNT), e.n(ROW)),
                    ),
                    e.mb.set(_cell(e, CELL_BUF), e.v("moved")),
                    e.mb.set(_cell(e, CELL_CAP), e.v("cap")),
                ),
            ),
        )
    )
    # level(op, first, rows): records rows `first` onwards as a level (op 0 added them, 1 removed
    # them), so undo and redo can remove or restore them.
    level_body = e.stage(
        e.seq(
            e.let("len", e.mb.operator_add(e.mb.operator_mul(e.v("rows"), e.n(ROW)), e.n(LEVEL_HEADER))),
            e.let("lvl", _fn(e, "bump", e.v("len"))),
            e.mb.set(e.mb.field(_f64p(e, e.v("lvl")), e.n(0)), _f64(e, e.v("op"))),
            e.mb.set(e.mb.field(_f64p(e, e.v("lvl")), e.n(1)), _f64(e, e.v("rows"))),
            _fn(
                e,
                "memory_copy",
                e.mb.operator_add(e.v("lvl"), e.n(LEVEL_HEADER)),
                e.mb.operator_add(_cell(e, CELL_BUF), e.mb.operator_mul(e.v("first"), e.n(ROW))),
                e.mb.operator_mul(e.v("rows"), e.n(ROW)),
            ),
            _host(e, "doc_edit", e.v("lvl"), e.v("len")),
        )
    )
    # redraw(): the strokes in the document, a segment per move row after a down row.
    redraw_body = e.stage(
        e.seq(
            _host(e, "canvas_clear"),
            e.let("i", e.mb.as_(e.n(0), e.lower(e.v("t_i32")))),
            e.let("px", _f64(e, e.n(0))),
            e.let("py", _f64(e, e.n(0))),
            e.let("buf", _cell(e, CELL_BUF)),
            _loop(
                e,
                "rows",
                e.seq(
                    e.if_only(e.mb.operator_ge(e.v("i"), _cell(e, CELL_COUNT)), e.mb.return_label("rows")),
                    e.let("kind", _row_field(e, e.v("buf"), e.v("i"), ROW_KIND)),
                    e.let("x", _row_field(e, e.v("buf"), e.v("i"), ROW_X)),
                    e.let("y", _row_field(e, e.v("buf"), e.v("i"), ROW_Y)),
                    e.if_only(
                        e.eq(_i32(e, e.v("kind")), e.n(1)),
                        _host(
                            e,
                            "canvas_segment",
                            e.v("px"),
                            e.v("py"),
                            e.v("x"),
                            e.v("y"),
                            e.mb.operator_add(
                                e.mb.operator_mul(_row_field(e, e.v("buf"), e.v("i"), ROW_P), e.n(6)), e.n(1)
                            ),
                            e.n(COLOR),
                        ),
                    ),
                    e.mb.set(e.v("px"), e.v("x")),
                    e.mb.set(e.v("py"), e.v("y")),
                    e.mb.set(e.v("i"), e.mb.operator_add(e.v("i"), e.n(1))),
                ),
            ),
        )
    )
    start_body = e.stage(
        e.seq(
            e.mb.set(_cell(e, CELL_HEAP), e.lower(e.v("heap"))),
            e.mb.set(_cell(e, CELL_BUF), _fn(e, "bump", e.n(0))),
            e.mb.set(
                _cell(e, CELL_CLEAR),
                _host(e, "button_add", e.lower(e.v("clear_label")), e.n(len(CLEAR.encode()))),
            ),
            _host(
                e,
                "doc_open",
                e.lower(e.v("doc_name")),
                e.n(len(DOC.encode())),
                e.lower(e.v("doc_key")),
                e.n(len(DOC_KEY.encode())),
            ),
        )
    )
    pointer_body = e.stage(
        e.seq(
            e.if_only(e.eq(_cell(e, CELL_COUNT), e.n(0)), e.mb.set(_float(e, FLOAT_T0), e.v("t"))),
            e.if_only(e.eq(e.v("kind"), e.n(0)), e.mb.set(_cell(e, CELL_START), _cell(e, CELL_COUNT))),
            _fn(e, "reserve", e.n(1)),
            e.let("n", _cell(e, CELL_COUNT)),
            e.let("buf", _cell(e, CELL_BUF)),
            e.mb.set(_row_field(e, e.v("buf"), e.v("n"), ROW_T), e.mb.operator_sub(e.v("t"), _float(e, FLOAT_T0))),
            e.mb.set(_row_field(e, e.v("buf"), e.v("n"), ROW_KIND), _f64(e, e.v("kind"))),
            e.mb.set(_row_field(e, e.v("buf"), e.v("n"), ROW_X), e.v("x")),
            e.mb.set(_row_field(e, e.v("buf"), e.v("n"), ROW_Y), e.v("y")),
            e.mb.set(_row_field(e, e.v("buf"), e.v("n"), ROW_P), e.v("p")),
            e.mb.set(_row_field(e, e.v("buf"), e.v("n"), 5), e.v("tx")),
            e.mb.set(_row_field(e, e.v("buf"), e.v("n"), 6), e.v("ty")),
            e.mb.set(_cell(e, CELL_COUNT), e.mb.operator_add(e.v("n"), e.n(1))),
            e.if_only(
                e.eq(e.v("kind"), e.n(0)),
                e.seq(
                    e.mb.set(_float(e, FLOAT_PREV_X), e.v("x")),
                    e.mb.set(_float(e, FLOAT_PREV_Y), e.v("y")),
                    e.mb.set(_cell(e, CELL_DOWN), e.n(1)),
                ),
            ),
            e.if_only(
                e.eq(e.v("kind"), e.n(1)),
                e.if_only(
                    e.eq(_cell(e, CELL_DOWN), e.n(1)),
                    e.seq(
                        _host(
                            e,
                            "canvas_segment",
                            _float(e, FLOAT_PREV_X),
                            _float(e, FLOAT_PREV_Y),
                            e.v("x"),
                            e.v("y"),
                            e.mb.operator_add(e.mb.operator_mul(e.v("p"), e.n(6)), e.n(1)),
                            e.n(COLOR),
                        ),
                        e.mb.set(_float(e, FLOAT_PREV_X), e.v("x")),
                        e.mb.set(_float(e, FLOAT_PREV_Y), e.v("y")),
                    ),
                ),
            ),
            e.if_only(
                e.eq(e.v("kind"), e.n(2)),
                e.seq(
                    e.mb.set(_cell(e, CELL_DOWN), e.n(0)),
                    _fn(
                        e,
                        "level",
                        e.n(0),
                        _cell(e, CELL_START),
                        e.mb.operator_sub(_cell(e, CELL_COUNT), _cell(e, CELL_START)),
                    ),
                ),
            ),
        )
    )
    button_body = e.stage(
        e.if_only(
            e.eq(e.v("id"), _cell(e, CELL_CLEAR)),
            e.seq(
                _fn(e, "level", e.n(1), e.n(0), _cell(e, CELL_COUNT)),
                e.mb.set(_cell(e, CELL_COUNT), e.n(0)),
                e.mb.set(_cell(e, CELL_DOWN), e.n(0)),
                _host(e, "canvas_clear"),
            ),
        )
    )
    alloc_body = e.stage(e.seq(e.ret(_fn(e, "bump", e.v("size")))))
    doc_ptr_body = e.stage(e.seq(e.ret(_cell(e, CELL_BUF))))
    doc_len_body = e.stage(e.seq(e.ret(e.mb.operator_mul(_cell(e, CELL_COUNT), e.n(ROW)))))
    # The delivered bytes become the document in place: they came from alloc, so they sit at the
    # end of what was handed out.
    on_doc_body = e.stage(
        e.seq(
            e.mb.set(_cell(e, CELL_BUF), e.v("ptr")),
            e.mb.set(_cell(e, CELL_COUNT), e.mb.operator_div(e.v("len"), e.n(ROW))),
            e.mb.set(_cell(e, CELL_CAP), e.mb.operator_div(e.v("len"), e.n(ROW))),
            e.mb.set(_cell(e, CELL_DOWN), e.n(0)),
            _fn(e, "redraw"),
        )
    )
    # A level's rows go back on when redoing an addition (op 0) or undoing a removal (op 1), and
    # come off otherwise.
    on_level_body = e.stage(
        e.seq(
            e.let("op", _i32(e, e.mb.field(_f64p(e, e.v("ptr")), e.n(0)))),
            e.let("rows", _i32(e, e.mb.field(_f64p(e, e.v("ptr")), e.n(1)))),
            e.if_only(
                e.eq(e.mb.operator_xor(e.v("op"), e.v("redo")), e.n(0)),
                e.mb.set(_cell(e, CELL_COUNT), e.mb.operator_sub(_cell(e, CELL_COUNT), e.v("rows"))),
            ),
            e.if_only(
                e.eq(e.mb.operator_xor(e.v("op"), e.v("redo")), e.n(1)),
                e.seq(
                    _fn(e, "reserve", e.v("rows")),
                    _fn(
                        e,
                        "memory_copy",
                        e.mb.operator_add(_cell(e, CELL_BUF), e.mb.operator_mul(_cell(e, CELL_COUNT), e.n(ROW))),
                        e.mb.operator_add(e.v("ptr"), e.n(LEVEL_HEADER)),
                        e.mb.operator_mul(e.v("rows"), e.n(ROW)),
                    ),
                    e.mb.set(_cell(e, CELL_COUNT), e.mb.operator_add(_cell(e, CELL_COUNT), e.v("rows"))),
                ),
            ),
            e.mb.set(_cell(e, CELL_DOWN), e.n(0)),
            _fn(e, "redraw"),
        )
    )
    functions = [
        ("bump", ["size"], "i32_i32_fn_t", bump_body),
        ("reserve", ["rows"], "i32_fn_t", reserve_body),
        ("level", ["op", "first", "rows"], "i32_i32_i32_void_fn_t", level_body),
        ("redraw", [], "void_fn_t", redraw_body),
        ("_start", [], "void_fn_t", start_body),
        ("on_pointer", ["kind", "x", "y", "p", "tx", "ty", "t"], "pointer_fn_t", pointer_body),
        ("on_button", ["id"], "i32_fn_t", button_body),
        ("alloc", ["size"], "i32_i32_fn_t", alloc_body),
        ("doc_ptr", [], "ret_i32_fn_t", doc_ptr_body),
        ("doc_len", [], "ret_i32_fn_t", doc_len_body),
        ("on_doc", ["ptr", "len"], "i32_i32_void_fn_t", on_doc_body),
        ("on_level", ["ptr", "len", "redo"], "i32_i32_i32_void_fn_t", on_level_body),
    ]
    for name, params, ty, body in functions:
        param_names = []
        for param in params:
            param_names.append(e.s(param))
        top.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "func_fn"),
                    e.rec(
                        e.p("mod", e.v("m")),
                        e.p("name", e.s(name)),
                        e.p("params", e.tup(*param_names)),
                        e.p("ty", e.v(ty)),
                        e.p("body", body),
                    ),
                ),
            )
        )
    for name in EXPORTS:
        top.append(e.call_m(e.v("m"), "export", e.s(name)))
    top.append(e.ret(e.call(e.fld(e.v("editor"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
