"""srcmap.atz: the frame table a target writes beside its code, the compile-time traceback of every emitted line.

A location (`types.qexpr_id`) is a chain: the expression itself, then the site of each expansion that produced it,
outermost last. The table interns every link of every chain it is given as a frame `{source, expr, parent}` (the
expression's source and id, and the frame of the expansion site that produced it, or none at the root) and hands
back the index of the innermost one. A target's standard, single-level debug map (a JS source map, DWARF lines,
binaryen annotations) then names a frame index as its "line", and the table's `render` is the sidecar that turns
those indices back into locations.

    new(())                 an empty table
    table.index(loc) -> int the frame of `loc`, interned with its whole chain
    table.count(()) -> int  the number of frames so far
    table.render(()) -> str the sidecar json: {"sources": [ids], "frames": [{"source", "expr", "parent"}]},
                            `expr` and `parent` null when absent

Frame indices are stable once handed out, so a target may intern as it emits and render at the end.
"""

from ..eco_mb import p
from ..target_mb import def_obj, in_, method, mk, push

FILE = "srcmap.atz"


def _int_list(e):
    return e.list_type(e.mb.types_int())


def _int_map(e):
    return e.map_type(e.mb.types_string(), e.mb.types_int_box())


def _table_t(e):
    return e.fld(e.v("table"), "type")


def _cell(e, name, value):
    return e.let(name, e.rec(p("v", value)))


def _cv(e, name):
    return e.fld(e.v(name), "v")


def _get_int(e, map_, key):
    return e.mb.as_(e.call_m(map_, "get", key), e.mb.types_int())


def _put(e, map_, key, value):
    return e.call_m(map_, "put", e.tup(key, value))


def _or_null(e, v):
    return e.if_else(e.mb.operator_lt(v, e.int_of(0)), e.dstr("null"), e.to_str(v))


def _index_body(e):
    loc_t = e.types_loc()
    return e.seq(
        # The chain innermost first, then folded from its root so each frame's parent is interned before it.
        e.let("chain", e.list_new(loc_t)),
        _cell(e, "cur", e.opt_some(loc_t, e.v("arg"))),
        e.mb.labeled(
            "walk",
            e.mb.loop(
                e.seq(
                    e.if_only(e.not_(e.fld(_cv(e, "cur"), "is_some")), e.mb.return_label("walk")),
                    push(e, e.v("chain"), e.fld(_cv(e, "cur"), "value")),
                    e.mb.set(_cv(e, "cur"), e.fld(_cv(e, "cur"), "value", "site")),
                )
            ),
        ),
        _cell(e, "parent", e.int_of(-1)),
        _cell(e, "j", e.mb.operator_sub(e.fld(e.v("chain"), "len"), e.int_of(1))),
        e.mb.labeled(
            "fold",
            e.mb.loop(
                e.seq(
                    e.if_only(e.mb.operator_lt(_cv(e, "j"), e.int_of(0)), e.mb.return_label("fold")),
                    e.let("l", e.call_m(e.v("chain"), "get", _cv(e, "j"))),
                    e.let("src", e.fld(e.v("l"), "source", "value")),
                    e.let(
                        "ex",
                        e.if_else(e.fld(e.v("l"), "expr", "is_some"), e.fld(e.v("l"), "expr", "value"), e.int_of(-1)),
                    ),
                    e.let(
                        "key",
                        e.cat(
                            e.to_str(e.v("src")),
                            e.s(":"),
                            e.to_str(e.v("ex")),
                            e.s(":"),
                            e.to_str(_cv(e, "parent")),
                        ),
                    ),
                    e.if_else(
                        e.call_m(in_(e, "keys"), "has", e.v("key")),
                        e.mb.set(_cv(e, "parent"), _get_int(e, in_(e, "keys"), e.v("key"))),
                        e.seq(
                            e.let("idx", e.fld(in_(e, "f_source"), "len")),
                            push(e, in_(e, "f_source"), e.v("src")),
                            push(e, in_(e, "f_expr"), e.v("ex")),
                            push(e, in_(e, "f_parent"), _cv(e, "parent")),
                            _put(e, in_(e, "keys"), e.v("key"), e.v("idx")),
                            e.mb.set(_cv(e, "parent"), e.v("idx")),
                            e.let("sk", e.to_str(e.v("src"))),
                            e.if_only(
                                e.not_(e.call_m(in_(e, "seen"), "has", e.v("sk"))),
                                e.seq(
                                    push(e, in_(e, "sources"), e.v("src")),
                                    _put(e, in_(e, "seen"), e.v("sk"), e.int_of(0)),
                                ),
                            ),
                        ),
                    ),
                    e.mb.set(_cv(e, "j"), e.mb.operator_sub(_cv(e, "j"), e.int_of(1))),
                )
            ),
        ),
        e.ret(_cv(e, "parent")),
    )


def _render_body(e):
    return e.seq(
        e.let("parts", e.list_new(e.mb.types_string())),
        _cell(e, "i", e.int_of(0)),
        e.foreach(
            in_(e, "f_source"),
            "s",
            e.seq(
                e.let("ex", e.call_m(in_(e, "f_expr"), "get", _cv(e, "i"))),
                e.let("par", e.call_m(in_(e, "f_parent"), "get", _cv(e, "i"))),
                push(
                    e,
                    e.v("parts"),
                    e.cat(
                        e.s('{"source":'),
                        e.to_str(e.v("s")),
                        e.s(',"expr":'),
                        _or_null(e, e.v("ex")),
                        e.s(',"parent":'),
                        _or_null(e, e.v("par")),
                        e.s("}"),
                    ),
                ),
                e.incr(_cv(e, "i")),
            ),
        ),
        e.let("srcs", e.list_new(e.mb.types_string())),
        e.foreach(in_(e, "sources"), "s", push(e, e.v("srcs"), e.to_str(e.v("s")))),
        e.ret(
            e.cat(
                e.s('{"sources":['),
                e.join(e.v("srcs"), ","),
                e.s('],"frames":['),
                e.join(e.v("parts"), ","),
                e.s("]}\n"),
            )
        ),
    )


def module(e):
    top = []
    top.append(e.let("d", e.define()))
    top.append(e.option_type_let())
    def_obj(
        e,
        top,
        "table",
        "source map frame table",
        e.rec(
            p("sources", _int_list(e)),
            p("seen", _int_map(e)),
            p("f_source", _int_list(e)),
            p("f_expr", _int_list(e)),
            p("f_parent", _int_list(e)),
            p("keys", _int_map(e)),
        ),
    )
    method(e, top, "table", "index", e.types_loc(), e.mb.types_int(), _index_body(e))
    method(e, top, "table", "count", e.tup(), e.mb.types_int(), e.fld(in_(e, "f_source"), "len"))
    method(e, top, "table", "render", e.tup(), e.mb.types_string(), _render_body(e))
    top.append(e.let("new_b", e.def_func(e.v("d"), "srcmap.new")))
    top.append(
        e.func_impl(
            e.v("new_b"),
            e.tup(),
            e.option_type_some(_table_t(e)),
            e.mb.opt_none_type(),
            e.stage(
                mk(
                    e,
                    "table",
                    p("sources", e.list_new(e.mb.types_int())),
                    p("seen", e.map_new(e.mb.types_string(), e.mb.types_int_box())),
                    p("f_source", e.list_new(e.mb.types_int())),
                    p("f_expr", e.list_new(e.mb.types_int())),
                    p("f_parent", e.list_new(e.mb.types_int())),
                    p("keys", e.map_new(e.mb.types_string(), e.mb.types_int_box())),
                )
            ),
        )
    )
    top.append(e.finish(e.v("d")))
    top.append(e.ret(e.rec(p("table_t", _table_t(e)), p("new", e.fld(e.v("new_b"), "func")))))
    return top
