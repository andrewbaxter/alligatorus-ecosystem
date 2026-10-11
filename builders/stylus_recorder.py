"""stylus-recorder.atz: a merman editor pane recording stylus samples and drawing the strokes.

Every pointer sample (time since the first sample, position, pressure, tilt) goes into a buffer, and
while the stylus is down each move draws a segment whose width follows the pressure. The clear
button empties the canvas and the buffer.
"""

from .merman_editor import FILE as EDITOR_FILE
from .wat import bind_types

CAPACITY = 4096
FIELDS = 6
COLOR = 0xE0C060FF
CLEAR = "Clear"
HOST = ["canvas_clear", "canvas_segment", "button_add"]

# cells: sample count, stylus down, the clear button's id
CELL_COUNT = 0
CELL_DOWN = 1
CELL_CLEAR = 2
# floats: previous x, previous y, the first sample's time; samples follow
FLOAT_PREV_X = 0
FLOAT_PREV_Y = 1
FLOAT_T0 = 2
FLOAT_SAMPLES = 8


def _cell(e, index):
    return e.mb.field(e.lower(e.v("cells")), e.n(index))


def _float(e, index):
    return e.mb.field(e.v("floats"), e.n(index) if isinstance(index, int) else index)


def _host(e, name, *args):
    return e.call(e.lower(e.v(name)), e.tup(*args))


def _fn_t(e, params, ret):
    param_types = []
    for param in params:
        param_types.append(e.v("t_" + param))
    return e.call(
        e.fld(e.v("wasm"), "fn"),
        e.rec(e.p("params", e.list_new(e.mb.eval_type(), *param_types)), e.p("ret", e.v("t_" + ret))),
    )


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("t_pf64", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_f64"))))
    setup.append(e.let("start_fn_t", _fn_t(e, [], "void")))
    setup.append(e.let("pointer_fn_t", _fn_t(e, ["i32", "f64", "f64", "f64", "f64", "f64", "f64"], "void")))
    setup.append(e.let("button_fn_t", _fn_t(e, ["i32"], "void")))
    setup.append(e.let("editor", e.import_local("editor", EDITOR_FILE)))
    exported = ["m", "start_fn_t", "pointer_fn_t", "button_fn_t", "t_i32", "t_f64", "t_pf64"]
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
    top.append(
        e.let(
            "cells",
            e.call(
                e.fld(e.v("wasm"), "data_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("cells")),
                    e.p("elem", e.v("t_i32")),
                    e.p("values", e.tup(e.n(0), e.n(0), e.n(0))),
                ),
            ),
        )
    )
    top.append(
        e.let(
            "buffer",
            e.call(
                e.fld(e.v("wasm"), "alloc_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("buffer")),
                    e.p("size", e.n((FLOAT_SAMPLES + CAPACITY * FIELDS) * 8)),
                ),
            ),
        )
    )
    top.append(e.let("clear_label", e.call_m(e.v("m"), "cstr", e.s(CLEAR))))
    floats = e.let("floats", e.mb.as_(e.lower(e.v("buffer")), e.lower(e.v("t_pf64"))))
    start_body = e.stage(
        e.seq(
            e.mb.set(
                _cell(e, CELL_CLEAR),
                _host(e, "button_add", e.lower(e.v("clear_label")), e.n(len(CLEAR.encode()))),
            )
        )
    )
    pointer_body = e.stage(
        e.seq(
            floats,
            e.let("n", _cell(e, CELL_COUNT)),
            e.if_only(
                e.mb.operator_lt(e.v("n"), e.n(CAPACITY)),
                e.seq(
                    e.if_only(e.eq(e.v("n"), e.n(0)), e.mb.set(_float(e, FLOAT_T0), e.v("t"))),
                    e.let("i", e.mb.operator_add(e.mb.operator_mul(e.v("n"), e.n(FIELDS)), e.n(FLOAT_SAMPLES))),
                    e.mb.set(_float(e, e.v("i")), e.mb.operator_sub(e.v("t"), _float(e, FLOAT_T0))),
                    e.mb.set(_float(e, e.mb.operator_add(e.v("i"), e.n(1))), e.v("x")),
                    e.mb.set(_float(e, e.mb.operator_add(e.v("i"), e.n(2))), e.v("y")),
                    e.mb.set(_float(e, e.mb.operator_add(e.v("i"), e.n(3))), e.v("p")),
                    e.mb.set(_float(e, e.mb.operator_add(e.v("i"), e.n(4))), e.v("tx")),
                    e.mb.set(_float(e, e.mb.operator_add(e.v("i"), e.n(5))), e.v("ty")),
                    e.mb.set(_cell(e, CELL_COUNT), e.mb.operator_add(e.v("n"), e.n(1))),
                ),
            ),
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
            e.if_only(e.eq(e.v("kind"), e.n(2)), e.mb.set(_cell(e, CELL_DOWN), e.n(0))),
        )
    )
    button_body = e.stage(
        e.if_only(
            e.eq(e.v("id"), _cell(e, CELL_CLEAR)),
            e.seq(
                _host(e, "canvas_clear"),
                e.mb.set(_cell(e, CELL_COUNT), e.n(0)),
                e.mb.set(_cell(e, CELL_DOWN), e.n(0)),
            ),
        )
    )
    for name, params, ty, body in [
        ("_start", [], "start_fn_t", start_body),
        ("on_pointer", ["kind", "x", "y", "p", "tx", "ty", "t"], "pointer_fn_t", pointer_body),
        ("on_button", ["id"], "button_fn_t", button_body),
    ]:
        param_names = []
        for param in params:
            param_names.append(e.s(param))
        top.append(
            e.call(
                e.fld(e.v("wasm"), "func_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s(name)),
                    e.p("params", e.tup(*param_names)),
                    e.p("ty", e.v(ty)),
                    e.p("body", body),
                ),
            )
        )
        top.append(e.call_m(e.v("m"), "export", e.s(name)))
    top.append(e.ret(e.call(e.fld(e.v("editor"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
