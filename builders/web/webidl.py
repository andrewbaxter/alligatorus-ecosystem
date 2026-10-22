"""webidl.atz: WebIDL spec parser, definition table, and the shared `sig` ABI over it.

A signature names the interface of every handle it carries: `iparam.iface` for a handle-kinded parameter and
`isig.ret_iface` for a handle-kinded return (the interface definition's name, or "" for any handle: unions, mixins,
callbacks and strings handed over as handles); `ancestor({table, iface, of})` is the spec's inheritance (`parent`
chain, "" above all), which the wasm side turns into handle upcasts."""

from .. import target_mb
from ..target_mb import (
    a,
    accessor,
    and_b,
    body,
    count_let,
    count_loop,
    bool_t,
    def_iface,
    def_obj,
    dfalse,
    fn_impl,
    hf,
    in_,
    int_t,
    lt,
    lv,
    marker_type,
    mk,
    num,
    or_b,
    push,
    ret_m,
    str_,
    t,
    to_str,
)

SPEC_REPO = "https://github.com/w3c/webref"

SPEC_COMMIT = "8a9e087aee12097e86b036b8560b6b0217f784eb"

SPEC_FILES = ["dom.idl", "html.idl", "cssom-view.idl", "webgl1.idl", "webgl2.idl"]


def _fn_def(e, out, name, arg_type, ret):
    return target_mb.fn_def(e, out, "webidl", name, arg_type, ret)


def _fn_impl_void(e, out, name, body_expr):
    sig = e.fn_sigs.pop(name)
    out.append(e.func_impl(e.v(name + "_b"), sig[0], e.option_type_none(), sig[2], e.stage(body_expr)))


def _lex_t(e):
    return t(e, "lex")


def _cur_t(e):
    return t(e, "cur")


def _lc(e):
    return e.rec(e.p("lex", _lex_t(e)), e.p("cur", _cur_t(e)))


def _lc_args(e, *extra):
    return e.rec(e.p("lex", a(e, "lex")), e.p("cur", a(e, "cur")), *extra)


def _peek(e):
    return hf(e, "h_peek", _lc_args(e))


def _next(e):
    return hf(e, "h_next", _lc_args(e))


def _next_text(e):
    return e.call_m(_next(e), "text", e.tup())


def _accept(e, text):
    return hf(e, "h_accept", _lc_args(e, e.p("text", e.s(text))))


def _expect(e, text):
    return hf(e, "h_expect", _lc_args(e, e.p("text", e.s(text))))


def _skip_balanced(e, close):
    return hf(e, "h_skip_balanced", _lc_args(e, e.p("close", e.s(close))))


def _parse_type(e):
    return hf(e, "h_type", _lc_args(e))


def _byte_is(e, n, c):
    return e.eq(n, num(e, ord(c)))


def _sig_of(e):
    return mk(
        e,
        "isig",
        e.p("ok", e.eq(e.fld(e.v("st"), "ok"), num(e, 1))),
        e.p("err", e.fld(e.v("st"), "err")),
        e.p("iface", e.fld(e.v("st"), "iface")),
        e.p("member", e.fld(e.v("st"), "member")),
        e.p("base", e.fld(e.v("st"), "base")),
        e.p("kind", a(e, "kind")),
        e.p("self", e.eq(e.fld(e.v("st"), "self"), num(e, 1))),
        e.p("args", e.v("args")),
        e.p("ret_out", e.eq(e.fld(e.v("st"), "ret_out"), num(e, 1))),
        e.p("ret_kind", e.fld(e.v("st"), "ret_kind")),
        e.p("ret_iface", e.fld(e.v("st"), "ret_iface")),
    )


def _sig_err(e, message):
    return e.seq(
        e.mb.set(e.fld(e.v("st"), "ok"), e.int_of(0)), e.mb.set(e.fld(e.v("st"), "err"), message), ret_m(e, _sig_of(e))
    )


def _sig_call(e, iface, member, kind):
    return hf(
        e,
        "h_sig",
        e.rec(e.p("table", a(e, "table")), e.p("iface", iface), e.p("member", member), e.p("kind", e.s(kind))),
    )


def _in_range(e, n, lo, hi):
    return and_b(e, e.mb.operator_ge(n, num(e, ord(lo))), e.mb.operator_le(n, num(e, ord(hi))))


def _utf8(e, bytes_):
    return e.match_of(
        e.call(e.eval_builtin("str_from_utf8"), bytes_),
        "__s",
        None,
        e.p("some", e.v("__s")),
        e.p("none", e.mb.panic(e.s("webidl: spec text is not valid UTF-8"))),
    )


def _itype(e, name, nullable, args):
    return mk(e, "itype", e.p("name", name), e.p("nullable", nullable), e.p("args", args))


def _imember(e, kind, name, ty, args, readonly, static_, special):
    return _imember_value(e, kind, name, ty, args, readonly, static_, special, e.dstr(""))


def _imember_value(e, kind, name, ty, args, readonly, static_, special, value):
    return mk(
        e,
        "imember",
        e.p("kind", kind),
        e.p("name", name),
        e.p("ty", ty),
        e.p("args", args),
        e.p("readonly", readonly),
        e.p("static_", static_),
        e.p("special", special),
        e.p("value", value),
    )


def _ifound(e, found, iface, member, count):
    return mk(e, "ifound", e.p("found", found), e.p("iface", iface), e.p("member", member), e.p("count", count))


def _no_member(e):
    return _imember(
        e, e.dstr(""), e.dstr(""), _no_type(e), e.list_new(lt(e, "iarg")), e.b(False), e.b(False), e.dstr("")
    )


BUF_NAMES = [
    "BufferSource",
    "AllowSharedBufferSource",
    "ArrayBuffer",
    "ArrayBufferView",
    "Int8Array",
    "Uint8Array",
    "Uint8ClampedArray",
    "Int16Array",
    "Uint16Array",
    "Int32Array",
    "Uint32Array",
    "Float32Array",
    "Float64Array",
    "DataView",
]


def _no_type(e):
    return _itype(e, e.dstr("undefined"), e.b(False), e.list_new(lt(e, "itype")))


def _idef(e, kind, name, parent, partial, members, ty):
    return mk(
        e,
        "idef",
        e.p("kind", kind),
        e.p("name", name),
        e.p("parent", parent),
        e.p("partial", partial),
        e.p("members", members),
        e.p("strings", e.list_new(str_(e))),
        e.p("ty", ty),
    )


def _push_def(e, def_):
    return push(e, a(e, "out"), def_)


def module(e):
    x = []
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    def_obj(e, x, "tok", "webidl token", e.rec(e.p("kind", str_(e)), e.p("text", str_(e))))
    accessor(e, x, "tok", "kind", str_(e))
    accessor(e, x, "tok", "text", str_(e))
    def_obj(
        e, x, "lex", "webidl token stream", e.rec(e.p("toks", e.map_type(str_(e), t(e, "tok"))), e.p("n", int_t(e)))
    )
    accessor(e, x, "lex", "toks", e.map_type(str_(e), t(e, "tok")))
    accessor(e, x, "lex", "n", int_t(e))
    def_obj(e, x, "cur", "webidl cursor", e.rec(e.p("i", int_t(e))))
    accessor(e, x, "cur", "i", int_t(e))
    x.append(e.method_impl(e.v("cur"), "adv", e.tup(), e.option_type_none(), e.stage(e.incr(in_(e, "i")))))
    def_obj(
        e,
        x,
        "itype",
        "webidl type",
        e.rec(e.p("name", str_(e)), e.p("nullable", bool_t(e)), e.p("args", e.list_type(t(e, "itype")))),
    )
    accessor(e, x, "itype", "name", str_(e))
    accessor(e, x, "itype", "nullable", bool_t(e))
    accessor(e, x, "itype", "args", e.list_type(t(e, "itype")))
    def_obj(
        e,
        x,
        "iarg",
        "webidl argument",
        e.rec(e.p("name", str_(e)), e.p("ty", t(e, "itype")), e.p("optional", bool_t(e)), e.p("variadic", bool_t(e))),
    )
    accessor(e, x, "iarg", "name", str_(e))
    accessor(e, x, "iarg", "ty", t(e, "itype"))
    accessor(e, x, "iarg", "optional", bool_t(e))
    accessor(e, x, "iarg", "variadic", bool_t(e))
    def_obj(
        e,
        x,
        "imember",
        "webidl member",
        e.rec(
            e.p("kind", str_(e)),
            e.p("name", str_(e)),
            e.p("ty", t(e, "itype")),
            e.p("args", e.list_type(t(e, "iarg"))),
            e.p("readonly", bool_t(e)),
            e.p("static_", bool_t(e)),
            e.p("special", str_(e)),
            e.p("value", str_(e)),
        ),
    )
    accessor(e, x, "imember", "value", str_(e))
    accessor(e, x, "imember", "kind", str_(e))
    accessor(e, x, "imember", "name", str_(e))
    accessor(e, x, "imember", "ty", t(e, "itype"))
    accessor(e, x, "imember", "args", e.list_type(t(e, "iarg")))
    accessor(e, x, "imember", "readonly", bool_t(e))
    accessor(e, x, "imember", "static_", bool_t(e))
    accessor(e, x, "imember", "special", str_(e))
    def_obj(
        e,
        x,
        "idef",
        "webidl definition",
        e.rec(
            e.p("kind", str_(e)),
            e.p("name", str_(e)),
            e.p("parent", str_(e)),
            e.p("partial", bool_t(e)),
            e.p("members", e.list_type(t(e, "imember"))),
            e.p("strings", e.list_type(str_(e))),
            e.p("ty", t(e, "itype")),
        ),
    )
    accessor(e, x, "idef", "kind", str_(e))
    accessor(e, x, "idef", "name", str_(e))
    accessor(e, x, "idef", "parent", str_(e))
    accessor(e, x, "idef", "partial", bool_t(e))
    accessor(e, x, "idef", "members", e.list_type(t(e, "imember")))
    accessor(e, x, "idef", "strings", e.list_type(str_(e)))
    accessor(e, x, "idef", "ty", t(e, "itype"))
    def_obj(
        e,
        x,
        "itable",
        "webidl definition table",
        e.rec(e.p("defs", e.map_type(str_(e), t(e, "idef"))), e.p("typedefs", e.map_type(str_(e), t(e, "itype")))),
    )
    accessor(e, x, "itable", "defs", e.map_type(str_(e), t(e, "idef")))
    accessor(e, x, "itable", "typedefs", e.map_type(str_(e), t(e, "itype")))
    def_obj(
        e,
        x,
        "ifound",
        "webidl member lookup",
        e.rec(e.p("found", bool_t(e)), e.p("iface", str_(e)), e.p("member", t(e, "imember")), e.p("count", int_t(e))),
    )
    accessor(e, x, "ifound", "found", bool_t(e))
    accessor(e, x, "ifound", "iface", str_(e))
    accessor(e, x, "ifound", "member", t(e, "imember"))
    accessor(e, x, "ifound", "count", int_t(e))
    def_obj(
        e,
        x,
        "iparam",
        "webidl abi parameter",
        e.rec(e.p("optional", bool_t(e)), e.p("nullable", bool_t(e)), e.p("kind", str_(e)), e.p("iface", str_(e))),
    )
    accessor(e, x, "iparam", "optional", bool_t(e))
    accessor(e, x, "iparam", "nullable", bool_t(e))
    accessor(e, x, "iparam", "kind", str_(e))
    accessor(e, x, "iparam", "iface", str_(e))
    def_obj(
        e,
        x,
        "isig",
        "webidl abi signature",
        e.rec(
            e.p("ok", bool_t(e)),
            e.p("err", str_(e)),
            e.p("iface", str_(e)),
            e.p("member", str_(e)),
            e.p("base", str_(e)),
            e.p("kind", str_(e)),
            e.p("self", bool_t(e)),
            e.p("args", e.list_type(t(e, "iparam"))),
            e.p("ret_out", bool_t(e)),
            e.p("ret_kind", str_(e)),
            e.p("ret_iface", str_(e)),
        ),
    )
    for f in ["ok", "self", "ret_out"]:
        accessor(e, x, "isig", f, bool_t(e))
    for f in ["err", "iface", "member", "base", "kind", "ret_kind", "ret_iface"]:
        accessor(e, x, "isig", f, str_(e))
    accessor(e, x, "isig", "args", e.list_type(t(e, "iparam")))
    for vo in ["tok", "lex", "cur", "itype", "iarg", "imember", "idef", "itable", "ifound", "iparam", "isig"]:
        def_iface(e, x, vo + "_m")
        marker_type(e, x, vo, vo, vo + "_m", e.aspect_dispatch(lv(e, vo + "_m_id")))
        x.append(e.impl_interface(e.v(vo), t(e, vo + "_m")))

    _fn_def(e, x, "h_lex", str_(e), _lex_t(e))
    _fn_def(e, x, "h_peek", _lc(e), str_(e))
    _fn_def(e, x, "h_next", _lc(e), t(e, "tok"))
    _fn_def(e, x, "h_accept", e.rec(e.p("lex", _lex_t(e)), e.p("cur", _cur_t(e)), e.p("text", str_(e))), bool_t(e))
    _fn_def(e, x, "h_expect", e.rec(e.p("lex", _lex_t(e)), e.p("cur", _cur_t(e)), e.p("text", str_(e))), e.tup())
    _fn_def(
        e, x, "h_skip_balanced", e.rec(e.p("lex", _lex_t(e)), e.p("cur", _cur_t(e)), e.p("close", str_(e))), e.tup()
    )
    _fn_def(e, x, "h_skip_ext", _lc(e), e.tup())
    _fn_def(e, x, "h_skip_to_semi", _lc(e), e.tup())
    _fn_def(e, x, "h_skip_default", _lc(e), e.tup())
    _fn_def(e, x, "h_type", _lc(e), t(e, "itype"))
    _fn_def(
        e,
        x,
        "h_type_args",
        e.rec(e.p("lex", _lex_t(e)), e.p("cur", _cur_t(e)), e.p("out", e.list_type(t(e, "itype")))),
        e.tup(),
    )
    _fn_def(
        e,
        x,
        "h_union_rest",
        e.rec(e.p("lex", _lex_t(e)), e.p("cur", _cur_t(e)), e.p("out", e.list_type(t(e, "itype")))),
        e.tup(),
    )
    _fn_def(
        e,
        x,
        "h_args",
        e.rec(e.p("lex", _lex_t(e)), e.p("cur", _cur_t(e)), e.p("out", e.list_type(t(e, "iarg")))),
        e.tup(),
    )
    _fn_def(e, x, "h_member", _lc(e), t(e, "imember"))
    _fn_def(
        e,
        x,
        "h_members",
        e.rec(e.p("lex", _lex_t(e)), e.p("cur", _cur_t(e)), e.p("out", e.list_type(t(e, "imember")))),
        e.tup(),
    )
    _fn_def(
        e,
        x,
        "h_enum_values",
        e.rec(e.p("lex", _lex_t(e)), e.p("cur", _cur_t(e)), e.p("out", e.list_type(str_(e)))),
        e.tup(),
    )
    _fn_def(
        e,
        x,
        "h_def",
        e.rec(e.p("lex", _lex_t(e)), e.p("cur", _cur_t(e)), e.p("out", e.list_type(t(e, "idef")))),
        bool_t(e),
    )
    _fn_def(
        e,
        x,
        "h_defs",
        e.rec(e.p("lex", _lex_t(e)), e.p("cur", _cur_t(e)), e.p("out", e.list_type(t(e, "idef")))),
        e.tup(),
    )
    _fn_def(e, x, "h_parse", str_(e), e.list_type(t(e, "idef")))
    _fn_def(e, x, "h_table", e.list_type(t(e, "idef")), t(e, "itable"))
    _fn_def(e, x, "h_has", e.rec(e.p("defs", e.map_type(str_(e), t(e, "idef"))), e.p("name", str_(e))), bool_t(e))
    _fn_def(
        e, x, "h_has_td", e.rec(e.p("typedefs", e.map_type(str_(e), t(e, "itype"))), e.p("name", str_(e))), bool_t(e)
    )
    _fn_def(e, x, "h_resolve", e.rec(e.p("table", t(e, "itable")), e.p("ty", t(e, "itype"))), t(e, "itype"))
    _fn_def(e, x, "h_kind", e.rec(e.p("table", t(e, "itable")), e.p("ty", t(e, "itype"))), str_(e))
    _fn_def(
        e,
        x,
        "h_param",
        e.rec(e.p("table", t(e, "itable")), e.p("ty", t(e, "itype")), e.p("optional", bool_t(e))),
        t(e, "iparam"),
    )
    _fn_def(
        e,
        x,
        "h_sig",
        e.rec(e.p("table", t(e, "itable")), e.p("iface", str_(e)), e.p("member", str_(e)), e.p("kind", str_(e))),
        t(e, "isig"),
    )
    _fn_def(e, x, "h_sig_name", e.rec(e.p("table", t(e, "itable")), e.p("name", str_(e))), t(e, "isig"))
    _fn_def(
        e,
        x,
        "h_handle_iface",
        e.rec(e.p("table", t(e, "itable")), e.p("kind", str_(e)), e.p("name", str_(e))),
        str_(e),
    )
    _fn_def(
        e,
        x,
        "h_ancestor",
        e.rec(e.p("table", t(e, "itable")), e.p("iface", str_(e)), e.p("of", str_(e))),
        bool_t(e),
    )
    _fn_def(
        e,
        x,
        "h_abi_ret",
        e.rec(e.p("table", t(e, "itable")), e.p("ty", t(e, "itype"))),
        e.rec(e.p("out", bool_t(e)), e.p("kind", str_(e)), e.p("iface", str_(e))),
    )
    _fn_def(
        e,
        x,
        "h_find",
        e.rec(
            e.p("table", t(e, "itable")),
            e.p("iface", str_(e)),
            e.p("member", str_(e)),
            e.p("kind", str_(e)),
            e.p("index", int_t(e)),
        ),
        t(e, "ifound"),
    )
    _fn_def(e, x, "h_mangle", e.rec(e.p("iface", str_(e)), e.p("member", str_(e)), e.p("kind", str_(e))), str_(e))
    _fn_def(e, x, "h_number", str_(e), e.types_double())
    _fn_def(
        e,
        x,
        "h_const_value",
        e.rec(e.p("table", t(e, "itable")), e.p("iface", str_(e)), e.p("member", str_(e))),
        e.types_double(),
    )
    _fn_def(e, x, "h_split_overload", str_(e), e.rec(e.p("base", str_(e)), e.p("index", int_t(e))))

    emit = e.seq(
        e.if_only(
            e.mb.operator_gt(e.fld(e.v("st"), "n"), num(e, 0)),
            e.seq(
                e.call_m(
                    e.v("toks"),
                    "put",
                    e.tup(
                        to_str(e, e.fld(e.v("st"), "count")),
                        mk(e, "tok", e.p("kind", e.dstr("id")), e.p("text", _utf8(e, e.fld(e.v("st"), "tok")))),
                    ),
                ),
                e.incr(e.fld(e.v("st"), "count")),
                e.mb.set(e.fld(e.v("st"), "tok"), e.list_new(e.mb.types_byte())),
                e.mb.set(e.fld(e.v("st"), "n"), e.int_of(0)),
            ),
        )
    )
    push_byte = e.seq(push(e, e.fld(e.v("st"), "tok"), e.v("b")), e.incr(e.fld(e.v("st"), "n")))
    emit_sym = e.seq(
        e.call_m(
            e.v("toks"),
            "put",
            e.tup(
                to_str(e, e.fld(e.v("st"), "count")),
                mk(
                    e,
                    "tok",
                    e.p("kind", e.dstr("sym")),
                    e.p("text", _utf8(e, e.list_new(e.mb.types_byte(), e.v("b")))),
                ),
            ),
        ),
        e.incr(e.fld(e.v("st"), "count")),
    )
    emit_str = e.seq(
        e.call_m(
            e.v("toks"),
            "put",
            e.tup(
                to_str(e, e.fld(e.v("st"), "count")),
                mk(e, "tok", e.p("kind", e.dstr("str")), e.p("text", _utf8(e, e.fld(e.v("st"), "tok")))),
            ),
        ),
        e.incr(e.fld(e.v("st"), "count")),
        e.mb.set(e.fld(e.v("st"), "tok"), e.list_new(e.mb.types_byte())),
        e.mb.set(e.fld(e.v("st"), "n"), e.int_of(0)),
    )
    is_word_char = or_b(
        e,
        _in_range(e, e.v("n"), "a", "z"),
        or_b(
            e,
            _in_range(e, e.v("n"), "A", "Z"),
            or_b(e, _in_range(e, e.v("n"), "0", "9"), or_b(e, _byte_is(e, e.v("n"), "_"), _byte_is(e, e.v("n"), "-"))),
        ),
    )
    numeric_word = and_b(
        e,
        e.mb.operator_gt(e.fld(e.v("st"), "n"), num(e, 0)),
        or_b(e, _in_range(e, e.fld(e.v("st"), "first"), "0", "9"), _byte_is(e, e.fld(e.v("st"), "first"), "-")),
    )
    is_space = or_b(
        e,
        _byte_is(e, e.v("n"), " "),
        or_b(e, _byte_is(e, e.v("n"), "\n"), or_b(e, _byte_is(e, e.v("n"), "\t"), _byte_is(e, e.v("n"), "\r"))),
    )
    plain = e.if_else(
        _byte_is(e, e.v("n"), "/"),
        e.seq(emit, e.mb.set(e.fld(e.v("st"), "mode"), e.int_of(1))),
        e.if_else(
            _byte_is(e, e.v("n"), '"'),
            e.seq(emit, e.mb.set(e.fld(e.v("st"), "mode"), e.int_of(4))),
            e.if_else(
                is_word_char,
                e.seq(
                    e.if_only(e.eq(e.fld(e.v("st"), "n"), num(e, 0)), e.mb.set(e.fld(e.v("st"), "first"), e.v("n"))),
                    push_byte,
                ),
                e.if_else(
                    and_b(e, _byte_is(e, e.v("n"), "."), numeric_word),
                    push_byte,
                    e.if_else(is_space, emit, e.seq(emit, emit_sym)),
                ),
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_lex",
        body(
            e,
            e.let("toks", e.map_new(str_(e), lt(e, "tok"))),
            e.let(
                "st",
                e.rec(
                    e.p("mode", e.int_of(0)),
                    e.p("tok", e.list_new(e.mb.types_byte())),
                    e.p("n", e.int_of(0)),
                    e.p("first", e.int_of(0)),
                    e.p("count", e.int_of(0)),
                ),
            ),
            e.foreach(
                e.call(e.mb.eval_str_utf8(), e.v("arg")),
                "b",
                e.seq(
                    e.let("n", e.mb.as_(e.v("b"), int_t(e))),
                    e.let("mode", e.fld(e.v("st"), "mode")),
                    e.if_else(
                        e.eq(e.v("mode"), num(e, 1)),
                        e.if_else(
                            _byte_is(e, e.v("n"), "/"),
                            e.mb.set(e.fld(e.v("st"), "mode"), e.int_of(2)),
                            e.if_else(
                                _byte_is(e, e.v("n"), "*"),
                                e.mb.set(e.fld(e.v("st"), "mode"), e.int_of(3)),
                                e.mb.panic(e.s("webidl: stray '/'")),
                            ),
                        ),
                        e.if_else(
                            e.eq(e.v("mode"), num(e, 2)),
                            e.if_only(_byte_is(e, e.v("n"), "\n"), e.mb.set(e.fld(e.v("st"), "mode"), e.int_of(0))),
                            e.if_else(
                                e.eq(e.v("mode"), num(e, 3)),
                                e.if_only(_byte_is(e, e.v("n"), "*"), e.mb.set(e.fld(e.v("st"), "mode"), e.int_of(5))),
                                e.if_else(
                                    e.eq(e.v("mode"), num(e, 5)),
                                    e.if_else(
                                        _byte_is(e, e.v("n"), "/"),
                                        e.mb.set(e.fld(e.v("st"), "mode"), e.int_of(0)),
                                        e.if_only(
                                            e.not_(_byte_is(e, e.v("n"), "*")),
                                            e.mb.set(e.fld(e.v("st"), "mode"), e.int_of(3)),
                                        ),
                                    ),
                                    e.if_else(
                                        e.eq(e.v("mode"), num(e, 4)),
                                        e.if_else(
                                            _byte_is(e, e.v("n"), '"'),
                                            e.seq(emit_str, e.mb.set(e.fld(e.v("st"), "mode"), e.int_of(0))),
                                            push_byte,
                                        ),
                                        plain,
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            emit,
            e.ret(mk(e, "lex", e.p("toks", e.v("toks")), e.p("n", e.fld(e.v("st"), "count")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_peek",
        body(
            e,
            e.if_only(
                e.mb.operator_ge(e.call_m(a(e, "cur"), "i", e.tup()), e.call_m(a(e, "lex"), "n", e.tup())),
                ret_m(e, e.dstr("")),
            ),
            e.ret(
                e.call_m(
                    e.call_m(
                        e.call_m(a(e, "lex"), "toks", e.tup()), "get", to_str(e, e.call_m(a(e, "cur"), "i", e.tup()))
                    ),
                    "text",
                    e.tup(),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_next",
        body(
            e,
            e.if_only(
                e.mb.operator_ge(e.call_m(a(e, "cur"), "i", e.tup()), e.call_m(a(e, "lex"), "n", e.tup())),
                e.mb.panic(e.s("webidl: unexpected end of input")),
            ),
            e.let(
                "t",
                e.call_m(e.call_m(a(e, "lex"), "toks", e.tup()), "get", to_str(e, e.call_m(a(e, "cur"), "i", e.tup()))),
            ),
            e.call_m(a(e, "cur"), "adv", e.tup()),
            e.ret(e.v("t")),
        ),
    )
    fn_impl(
        e,
        x,
        "h_accept",
        body(
            e,
            e.if_only(e.not_(e.eq(_peek(e), a(e, "text"))), ret_m(e, dfalse(e))),
            e.call_m(a(e, "cur"), "adv", e.tup()),
            e.ret(e.b(True)),
        ),
    )
    _fn_impl_void(
        e,
        x,
        "h_expect",
        e.seq(
            e.let("t", _next_text(e)),
            e.if_only(
                e.not_(e.eq(e.v("t"), a(e, "text"))),
                e.mb.panic(e.cat(e.s("webidl: expected '"), a(e, "text"), e.s("' but found '"), e.v("t"), e.s("'"))),
            ),
        ),
    )
    _fn_impl_void(
        e,
        x,
        "h_skip_balanced",
        e.seq(
            e.let("t", _next_text(e)),
            e.if_only(
                e.not_(e.eq(e.v("t"), a(e, "close"))),
                e.seq(
                    e.if_only(e.eq(e.v("t"), e.s("(")), _skip_balanced(e, ")")),
                    e.if_only(e.eq(e.v("t"), e.s("[")), _skip_balanced(e, "]")),
                    e.if_only(e.eq(e.v("t"), e.s("{")), _skip_balanced(e, "}")),
                    hf(e, "h_skip_balanced", _lc_args(e, e.p("close", a(e, "close")))),
                ),
            ),
        ),
    )
    _fn_impl_void(
        e, x, "h_skip_ext", e.if_only(_accept(e, "["), e.seq(_skip_balanced(e, "]"), hf(e, "h_skip_ext", _lc_args(e))))
    )
    _fn_impl_void(
        e,
        x,
        "h_skip_to_semi",
        e.seq(
            e.let("t", _next_text(e)),
            e.if_only(
                e.not_(e.eq(e.v("t"), e.s(";"))),
                e.seq(
                    e.if_only(e.eq(e.v("t"), e.s("(")), _skip_balanced(e, ")")),
                    e.if_only(e.eq(e.v("t"), e.s("[")), _skip_balanced(e, "]")),
                    e.if_only(e.eq(e.v("t"), e.s("{")), _skip_balanced(e, "}")),
                    hf(e, "h_skip_to_semi", _lc_args(e)),
                ),
            ),
        ),
    )
    _fn_impl_void(
        e,
        x,
        "h_skip_default",
        e.seq(
            e.let("p", _peek(e)),
            e.if_only(
                e.not_(or_b(e, e.eq(e.v("p"), e.s(",")), or_b(e, e.eq(e.v("p"), e.s(")")), e.eq(e.v("p"), e.s(";"))))),
                e.seq(
                    e.let("t", _next_text(e)),
                    e.if_only(e.eq(e.v("t"), e.s("(")), _skip_balanced(e, ")")),
                    e.if_only(e.eq(e.v("t"), e.s("[")), _skip_balanced(e, "]")),
                    e.if_only(e.eq(e.v("t"), e.s("{")), _skip_balanced(e, "}")),
                    hf(e, "h_skip_default", _lc_args(e)),
                ),
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_type",
        body(
            e,
            hf(e, "h_skip_ext", _lc_args(e)),
            e.let("first", _next_text(e)),
            e.let("name", e.rec(e.p("v", e.dstr("")))),
            e.let("args", e.list_new(lt(e, "itype"))),
            e.if_else(
                e.eq(e.v("first"), e.s("(")),
                e.seq(
                    e.mb.set(e.fld(e.v("name"), "v"), e.dstr("union")),
                    push(e, e.v("args"), _parse_type(e)),
                    hf(e, "h_union_rest", _lc_args(e, e.p("out", e.v("args")))),
                    _expect(e, ")"),
                ),
                e.seq(
                    e.mb.set(e.fld(e.v("name"), "v"), e.v("first")),
                    e.if_only(
                        or_b(e, e.eq(e.v("first"), e.s("unsigned")), e.eq(e.v("first"), e.s("unrestricted"))),
                        e.mb.set(e.fld(e.v("name"), "v"), e.cat(e.fld(e.v("name"), "v"), e.s(" "), _next_text(e))),
                    ),
                    e.if_only(
                        and_b(
                            e,
                            or_b(
                                e,
                                e.eq(e.fld(e.v("name"), "v"), e.s("long")),
                                e.eq(e.fld(e.v("name"), "v"), e.s("unsigned long")),
                            ),
                            e.eq(_peek(e), e.s("long")),
                        ),
                        e.mb.set(e.fld(e.v("name"), "v"), e.cat(e.fld(e.v("name"), "v"), e.s(" "), _next_text(e))),
                    ),
                    e.if_only(
                        _accept(e, "<"),
                        e.seq(hf(e, "h_type_args", _lc_args(e, e.p("out", e.v("args")))), _expect(e, ">")),
                    ),
                ),
            ),
            e.let("nullable", _accept(e, "?")),
            e.ret(_itype(e, e.fld(e.v("name"), "v"), e.v("nullable"), e.v("args"))),
        ),
    )
    _fn_impl_void(
        e,
        x,
        "h_type_args",
        e.seq(
            push(e, a(e, "out"), _parse_type(e)),
            e.if_only(_accept(e, ","), hf(e, "h_type_args", _lc_args(e, e.p("out", a(e, "out"))))),
        ),
    )
    _fn_impl_void(
        e,
        x,
        "h_union_rest",
        e.if_only(
            _accept(e, "or"),
            e.seq(push(e, a(e, "out"), _parse_type(e)), hf(e, "h_union_rest", _lc_args(e, e.p("out", a(e, "out"))))),
        ),
    )
    _fn_impl_void(
        e,
        x,
        "h_args",
        e.if_only(
            e.not_(_accept(e, ")")),
            e.seq(
                hf(e, "h_skip_ext", _lc_args(e)),
                e.let("optional", _accept(e, "optional")),
                e.let("ty", _parse_type(e)),
                e.let("variadic", _accept(e, ".")),
                e.if_only(e.v("variadic"), e.seq(_expect(e, "."), _expect(e, "."))),
                e.let("name", _next_text(e)),
                e.if_only(_accept(e, "="), hf(e, "h_skip_default", _lc_args(e))),
                push(
                    e,
                    a(e, "out"),
                    mk(
                        e,
                        "iarg",
                        e.p("name", e.v("name")),
                        e.p("ty", e.v("ty")),
                        e.p("optional", e.v("optional")),
                        e.p("variadic", e.v("variadic")),
                    ),
                ),
                e.if_else(_accept(e, ","), hf(e, "h_args", _lc_args(e, e.p("out", a(e, "out")))), _expect(e, ")")),
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_member",
        body(
            e,
            hf(e, "h_skip_ext", _lc_args(e)),
            e.let("st", e.rec(e.p("readonly", e.int_of(0)), e.p("static_", e.int_of(0)), e.p("special", e.dstr("")))),
            e.if_only(_accept(e, "static"), e.mb.set(e.fld(e.v("st"), "static_"), e.int_of(1))),
            e.if_only(
                _accept(e, "stringifier"),
                e.if_only(
                    _accept(e, ";"),
                    ret_m(
                        e,
                        _imember(
                            e,
                            e.dstr("other"),
                            e.dstr("stringifier"),
                            _no_type(e),
                            e.list_new(lt(e, "iarg")),
                            e.b(False),
                            e.b(False),
                            e.dstr(""),
                        ),
                    ),
                ),
            ),
            e.if_only(_accept(e, "inherit"), e.seq()),
            e.if_only(_accept(e, "readonly"), e.mb.set(e.fld(e.v("st"), "readonly"), e.int_of(1))),
            e.if_only(_accept(e, "required"), e.seq()),
            e.if_only(_accept(e, "async"), e.seq()),
            e.if_only(_accept(e, "getter"), e.mb.set(e.fld(e.v("st"), "special"), e.dstr("getter"))),
            e.if_only(_accept(e, "setter"), e.mb.set(e.fld(e.v("st"), "special"), e.dstr("setter"))),
            e.if_only(_accept(e, "deleter"), e.mb.set(e.fld(e.v("st"), "special"), e.dstr("deleter"))),
            e.if_only(
                _accept(e, "const"),
                e.seq(
                    e.let("cty", _parse_type(e)),
                    e.let("cname", _next_text(e)),
                    _expect(e, "="),
                    e.let("cvalue", _next_text(e)),
                    _expect(e, ";"),
                    ret_m(
                        e,
                        _imember_value(
                            e,
                            e.dstr("const"),
                            e.v("cname"),
                            e.v("cty"),
                            e.list_new(lt(e, "iarg")),
                            e.b(True),
                            e.b(True),
                            e.dstr(""),
                            e.v("cvalue"),
                        ),
                    ),
                ),
            ),
            e.let("p", _peek(e)),
            e.if_only(
                or_b(
                    e,
                    e.eq(e.v("p"), e.s("iterable")),
                    or_b(e, e.eq(e.v("p"), e.s("maplike")), e.eq(e.v("p"), e.s("setlike"))),
                ),
                e.seq(
                    e.let("kw", _next_text(e)),
                    hf(e, "h_skip_to_semi", _lc_args(e)),
                    ret_m(
                        e,
                        _imember(
                            e,
                            e.dstr("other"),
                            e.v("kw"),
                            _no_type(e),
                            e.list_new(lt(e, "iarg")),
                            e.b(False),
                            e.b(False),
                            e.dstr(""),
                        ),
                    ),
                ),
            ),
            e.if_only(
                _accept(e, "constructor"),
                e.seq(
                    _expect(e, "("),
                    e.let("cargs", e.list_new(lt(e, "iarg"))),
                    hf(e, "h_args", _lc_args(e, e.p("out", e.v("cargs")))),
                    _expect(e, ";"),
                    ret_m(
                        e,
                        _imember(
                            e,
                            e.dstr("ctor"),
                            e.dstr("constructor"),
                            _no_type(e),
                            e.v("cargs"),
                            e.b(False),
                            e.b(False),
                            e.dstr(""),
                        ),
                    ),
                ),
            ),
            e.if_only(
                _accept(e, "attribute"),
                e.seq(
                    e.let("aty", _parse_type(e)),
                    e.let("aname", _next_text(e)),
                    _expect(e, ";"),
                    ret_m(
                        e,
                        _imember(
                            e,
                            e.dstr("attr"),
                            e.v("aname"),
                            e.v("aty"),
                            e.list_new(lt(e, "iarg")),
                            e.eq(e.fld(e.v("st"), "readonly"), num(e, 1)),
                            e.eq(e.fld(e.v("st"), "static_"), num(e, 1)),
                            e.fld(e.v("st"), "special"),
                        ),
                    ),
                ),
            ),
            e.let("ty", _parse_type(e)),
            e.let("name", e.if_else(e.eq(_peek(e), e.s("(")), e.dstr(""), _next_text(e))),
            e.if_only(_accept(e, "="), hf(e, "h_skip_default", _lc_args(e))),
            e.if_only(
                _accept(e, ";"),
                ret_m(
                    e,
                    _imember(
                        e,
                        e.dstr("field"),
                        e.v("name"),
                        e.v("ty"),
                        e.list_new(lt(e, "iarg")),
                        e.b(False),
                        e.b(False),
                        e.dstr(""),
                    ),
                ),
            ),
            _expect(e, "("),
            e.let("args", e.list_new(lt(e, "iarg"))),
            hf(e, "h_args", _lc_args(e, e.p("out", e.v("args")))),
            _expect(e, ";"),
            e.ret(
                _imember(
                    e,
                    e.dstr("op"),
                    e.v("name"),
                    e.v("ty"),
                    e.v("args"),
                    e.eq(e.fld(e.v("st"), "readonly"), num(e, 1)),
                    e.eq(e.fld(e.v("st"), "static_"), num(e, 1)),
                    e.fld(e.v("st"), "special"),
                )
            ),
        ),
    )
    _fn_impl_void(
        e,
        x,
        "h_members",
        e.if_only(
            e.not_(_accept(e, "}")),
            e.seq(
                push(e, a(e, "out"), hf(e, "h_member", _lc_args(e))),
                hf(e, "h_members", _lc_args(e, e.p("out", a(e, "out")))),
            ),
        ),
    )
    _fn_impl_void(
        e,
        x,
        "h_enum_values",
        e.seq(
            e.let("t", _next(e)),
            e.if_only(
                e.not_(e.eq(e.call_m(e.v("t"), "text", e.tup()), e.s("}"))),
                e.seq(
                    e.if_only(
                        e.eq(e.call_m(e.v("t"), "kind", e.tup()), e.s("str")),
                        push(e, a(e, "out"), e.call_m(e.v("t"), "text", e.tup())),
                    ),
                    hf(e, "h_enum_values", _lc_args(e, e.p("out", a(e, "out")))),
                ),
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_def",
        body(
            e,
            hf(e, "h_skip_ext", _lc_args(e)),
            e.if_only(e.eq(_peek(e), e.s("")), ret_m(e, dfalse(e))),
            e.let("partial", _accept(e, "partial")),
            e.let("kw", _next_text(e)),
            e.if_only(
                e.eq(e.v("kw"), e.s("interface")),
                e.seq(
                    e.let("mixin", _accept(e, "mixin")),
                    e.let("name", _next_text(e)),
                    e.let("parent", e.if_else(_accept(e, ":"), _next_text(e), e.dstr(""))),
                    _expect(e, "{"),
                    e.let("members", e.list_new(lt(e, "imember"))),
                    hf(e, "h_members", _lc_args(e, e.p("out", e.v("members")))),
                    _expect(e, ";"),
                    _push_def(
                        e,
                        _idef(
                            e,
                            e.if_else(e.v("mixin"), e.dstr("mixin"), e.dstr("interface")),
                            e.v("name"),
                            e.v("parent"),
                            e.v("partial"),
                            e.v("members"),
                            _no_type(e),
                        ),
                    ),
                    ret_m(e, e.b(True)),
                ),
            ),
            e.if_only(
                or_b(e, e.eq(e.v("kw"), e.s("dictionary")), e.eq(e.v("kw"), e.s("namespace"))),
                e.seq(
                    e.let("name", _next_text(e)),
                    e.let("parent", e.if_else(_accept(e, ":"), _next_text(e), e.dstr(""))),
                    _expect(e, "{"),
                    e.let("members", e.list_new(lt(e, "imember"))),
                    hf(e, "h_members", _lc_args(e, e.p("out", e.v("members")))),
                    _expect(e, ";"),
                    _push_def(
                        e,
                        _idef(e, e.v("kw"), e.v("name"), e.v("parent"), e.v("partial"), e.v("members"), _no_type(e)),
                    ),
                    ret_m(e, e.b(True)),
                ),
            ),
            e.if_only(
                e.eq(e.v("kw"), e.s("enum")),
                e.seq(
                    e.let("name", _next_text(e)),
                    _expect(e, "{"),
                    e.let(
                        "def",
                        _idef(
                            e,
                            e.dstr("enum"),
                            e.v("name"),
                            e.dstr(""),
                            e.b(False),
                            e.list_new(lt(e, "imember")),
                            _no_type(e),
                        ),
                    ),
                    hf(e, "h_enum_values", _lc_args(e, e.p("out", e.call_m(e.v("def"), "strings", e.tup())))),
                    _expect(e, ";"),
                    _push_def(e, e.v("def")),
                    ret_m(e, e.b(True)),
                ),
            ),
            e.if_only(
                e.eq(e.v("kw"), e.s("typedef")),
                e.seq(
                    e.let("ty", _parse_type(e)),
                    e.let("name", _next_text(e)),
                    _expect(e, ";"),
                    e.let(
                        "def",
                        _idef(
                            e,
                            e.dstr("typedef"),
                            e.v("name"),
                            e.dstr(""),
                            e.b(False),
                            e.list_new(lt(e, "imember")),
                            e.v("ty"),
                        ),
                    ),
                    _push_def(e, e.v("def")),
                    ret_m(e, e.b(True)),
                ),
            ),
            e.if_only(
                e.eq(e.v("kw"), e.s("callback")),
                e.seq(
                    e.if_only(
                        _accept(e, "interface"),
                        e.seq(
                            e.let("cname", _next_text(e)),
                            _expect(e, "{"),
                            e.let("cmembers", e.list_new(lt(e, "imember"))),
                            hf(e, "h_members", _lc_args(e, e.p("out", e.v("cmembers")))),
                            _expect(e, ";"),
                            _push_def(
                                e,
                                _idef(
                                    e,
                                    e.dstr("callback_interface"),
                                    e.v("cname"),
                                    e.dstr(""),
                                    e.b(False),
                                    e.v("cmembers"),
                                    _no_type(e),
                                ),
                            ),
                            ret_m(e, e.b(True)),
                        ),
                    ),
                    e.let("name", _next_text(e)),
                    _expect(e, "="),
                    e.let("ty", _parse_type(e)),
                    _expect(e, "("),
                    e.let("cargs", e.list_new(lt(e, "iarg"))),
                    hf(e, "h_args", _lc_args(e, e.p("out", e.v("cargs")))),
                    _expect(e, ";"),
                    e.let(
                        "def",
                        _idef(
                            e,
                            e.dstr("callback"),
                            e.v("name"),
                            e.dstr(""),
                            e.b(False),
                            e.list_new(lt(e, "imember")),
                            e.v("ty"),
                        ),
                    ),
                    _push_def(e, e.v("def")),
                    ret_m(e, e.b(True)),
                ),
            ),
            _expect(e, "includes"),
            e.let("target", _next_text(e)),
            _expect(e, ";"),
            _push_def(
                e,
                _idef(
                    e,
                    e.dstr("includes"),
                    e.v("kw"),
                    e.v("target"),
                    e.b(False),
                    e.list_new(lt(e, "imember")),
                    _no_type(e),
                ),
            ),
            e.ret(e.b(True)),
        ),
    )
    _fn_impl_void(
        e,
        x,
        "h_defs",
        e.if_only(
            hf(e, "h_def", _lc_args(e, e.p("out", a(e, "out")))), hf(e, "h_defs", _lc_args(e, e.p("out", a(e, "out"))))
        ),
    )
    fn_impl(
        e,
        x,
        "h_parse",
        body(
            e,
            e.let("lex", hf(e, "h_lex", e.v("arg"))),
            e.let("cur", mk(e, "cur", e.p("i", e.int_of(0)))),
            e.let("out", e.list_new(lt(e, "idef"))),
            hf(e, "h_defs", e.rec(e.p("lex", e.v("lex")), e.p("cur", e.v("cur")), e.p("out", e.v("out")))),
            e.ret(e.v("out")),
        ),
    )
    fn_impl(
        e,
        x,
        "h_has",
        body(
            e,
            e.foreach(
                a(e, "defs"),
                "en",
                e.if_only(e.eq(e.fld(e.v("en"), "key"), a(e, "name")), ret_m(e, e.mb.as_(e.b(True), bool_t(e)))),
            ),
            e.ret(dfalse(e)),
        ),
    )
    fn_impl(
        e,
        x,
        "h_has_td",
        body(
            e,
            e.foreach(
                a(e, "typedefs"),
                "en",
                e.if_only(e.eq(e.fld(e.v("en"), "key"), a(e, "name")), ret_m(e, e.mb.as_(e.b(True), bool_t(e)))),
            ),
            e.ret(dfalse(e)),
        ),
    )
    fn_impl(
        e,
        x,
        "h_resolve",
        body(
            e,
            e.let("tds", e.call_m(a(e, "table"), "typedefs", e.tup())),
            e.let("name", e.call_m(a(e, "ty"), "name", e.tup())),
            e.if_only(
                e.not_(hf(e, "h_has_td", e.rec(e.p("typedefs", e.v("tds")), e.p("name", e.v("name"))))),
                ret_m(e, a(e, "ty")),
            ),
            e.let(
                "r",
                hf(
                    e,
                    "h_resolve",
                    e.rec(e.p("table", a(e, "table")), e.p("ty", e.call_m(e.v("tds"), "get", e.v("name")))),
                ),
            ),
            e.ret(
                _itype(
                    e,
                    e.call_m(e.v("r"), "name", e.tup()),
                    or_b(e, e.call_m(a(e, "ty"), "nullable", e.tup()), e.call_m(e.v("r"), "nullable", e.tup())),
                    e.call_m(e.v("r"), "args", e.tup()),
                )
            ),
        ),
    )
    scalars = [
        ("DOMString", "str"),
        ("USVString", "str"),
        ("ByteString", "str"),
        ("CSSOMString", "str"),
        ("boolean", "bool"),
        ("byte", "i8"),
        ("octet", "u8"),
        ("short", "i16"),
        ("unsigned short", "u16"),
        ("long", "i32"),
        ("unsigned long", "u32"),
        ("long long", "i64"),
        ("unsigned long long", "u64"),
        ("float", "f32"),
        ("unrestricted float", "f32"),
        ("double", "f64"),
        ("unrestricted double", "f64"),
        ("undefined", "void"),
    ]
    kind_entries = []
    for idl_name, kind in scalars:
        kind_entries.append(e.p(idl_name, e.s(kind)))
    buf_entries = []
    for name in BUF_NAMES:
        buf_entries.append(e.p(name, e.s("buf")))
    fn_impl(
        e,
        x,
        "h_kind",
        body(
            e,
            e.let("bufs", e.map_new(str_(e), str_(e), *buf_entries)),
            e.if_only(e.call_m(e.v("bufs"), "has", e.call_m(a(e, "ty"), "name", e.tup())), ret_m(e, e.dstr("buf"))),
            e.let("r", hf(e, "h_resolve", e.rec(e.p("table", a(e, "table")), e.p("ty", a(e, "ty"))))),
            e.let("name", e.call_m(e.v("r"), "name", e.tup())),
            e.if_only(e.call_m(e.v("bufs"), "has", e.v("name")), ret_m(e, e.dstr("buf"))),
            e.if_only(
                e.eq(e.v("name"), e.s("union")),
                e.seq(
                    e.foreach(
                        e.call_m(e.v("r"), "args", e.tup()),
                        "ua",
                        e.if_only(
                            e.eq(hf(e, "h_kind", e.rec(e.p("table", a(e, "table")), e.p("ty", e.v("ua")))), e.s("str")),
                            ret_m(e, e.dstr("str")),
                        ),
                    ),
                    ret_m(e, e.dstr("handle")),
                ),
            ),
            e.let("scalars", e.map_new(str_(e), str_(e), *kind_entries)),
            e.foreach(
                e.v("scalars"),
                "en",
                e.if_only(e.eq(e.fld(e.v("en"), "key"), e.v("name")), ret_m(e, e.fld(e.v("en"), "value"))),
            ),
            e.let("defs", e.call_m(a(e, "table"), "defs", e.tup())),
            e.if_only(
                and_b(
                    e,
                    hf(e, "h_has", e.rec(e.p("defs", e.v("defs")), e.p("name", e.v("name")))),
                    e.eq(e.call_m(e.call_m(e.v("defs"), "get", e.v("name")), "kind", e.tup()), e.s("enum")),
                ),
                ret_m(e, e.dstr("str")),
            ),
            e.ret(e.dstr("handle")),
        ),
    )
    fn_impl(
        e,
        x,
        "h_param",
        body(
            e,
            e.let("r", hf(e, "h_resolve", e.rec(e.p("table", a(e, "table")), e.p("ty", a(e, "ty"))))),
            e.let("k", hf(e, "h_kind", e.rec(e.p("table", a(e, "table")), e.p("ty", a(e, "ty"))))),
            e.ret(
                mk(
                    e,
                    "iparam",
                    e.p("optional", a(e, "optional")),
                    e.p("nullable", e.call_m(e.v("r"), "nullable", e.tup())),
                    e.p("kind", e.v("k")),
                    e.p(
                        "iface",
                        hf(
                            e,
                            "h_handle_iface",
                            e.rec(
                                e.p("table", a(e, "table")),
                                e.p("kind", e.v("k")),
                                e.p("name", e.call_m(e.v("r"), "name", e.tup())),
                            ),
                        ),
                    ),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_abi_ret",
        body(
            e,
            e.let("r", hf(e, "h_resolve", e.rec(e.p("table", a(e, "table")), e.p("ty", a(e, "ty"))))),
            e.let("k", hf(e, "h_kind", e.rec(e.p("table", a(e, "table")), e.p("ty", a(e, "ty"))))),
            e.ret(
                e.rec(
                    e.p("out", e.call_m(e.v("r"), "nullable", e.tup())),
                    e.p("kind", e.v("k")),
                    e.p(
                        "iface",
                        hf(
                            e,
                            "h_handle_iface",
                            e.rec(
                                e.p("table", a(e, "table")),
                                e.p("kind", e.v("k")),
                                e.p("name", e.call_m(e.v("r"), "name", e.tup())),
                            ),
                        ),
                    ),
                )
            ),
        ),
    )
    # The interface a handle-kinded type names: an interface definition's name, else "" (any handle: unions, mixins
    # and the rest that JS hands over as a handle).
    fn_impl(
        e,
        x,
        "h_handle_iface",
        body(
            e,
            e.if_only(e.not_(e.eq(a(e, "kind"), e.s("handle"))), ret_m(e, e.dstr(""))),
            e.let("defs", e.call_m(a(e, "table"), "defs", e.tup())),
            e.if_only(
                e.not_(hf(e, "h_has", e.rec(e.p("defs", e.v("defs")), e.p("name", a(e, "name"))))), ret_m(e, e.dstr(""))
            ),
            e.if_only(
                e.not_(e.eq(e.call_m(e.call_m(e.v("defs"), "get", a(e, "name")), "kind", e.tup()), e.s("interface"))),
                ret_m(e, e.dstr("")),
            ),
            e.ret(a(e, "name")),
        ),
    )
    # Whether the interface `iface` is `of` or inherits from it (along `parent`); "" (any handle) is above every
    # interface.
    fn_impl(
        e,
        x,
        "h_ancestor",
        body(
            e,
            e.if_only(e.eq(a(e, "of"), e.s("")), ret_m(e, e.mb.as_(e.b(True), bool_t(e)))),
            e.if_only(e.eq(a(e, "iface"), a(e, "of")), ret_m(e, e.mb.as_(e.b(True), bool_t(e)))),
            e.let("defs", e.call_m(a(e, "table"), "defs", e.tup())),
            e.if_only(
                e.not_(hf(e, "h_has", e.rec(e.p("defs", e.v("defs")), e.p("name", a(e, "iface"))))),
                ret_m(e, e.mb.as_(e.b(False), bool_t(e))),
            ),
            e.let("parent", e.call_m(e.call_m(e.v("defs"), "get", a(e, "iface")), "parent", e.tup())),
            e.if_only(e.eq(e.v("parent"), e.s("")), ret_m(e, e.mb.as_(e.b(False), bool_t(e)))),
            e.ret(
                hf(
                    e,
                    "h_ancestor",
                    e.rec(e.p("table", a(e, "table")), e.p("iface", e.v("parent")), e.p("of", a(e, "of"))),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_find",
        body(
            e,
            e.let("defs", e.call_m(a(e, "table"), "defs", e.tup())),
            e.let("none", _ifound(e, e.b(False), e.dstr(""), _no_member(e), e.int_of(0))),
            e.if_only(
                e.not_(hf(e, "h_has", e.rec(e.p("defs", e.v("defs")), e.p("name", a(e, "iface"))))),
                ret_m(e, e.v("none")),
            ),
            e.let("def", e.call_m(e.v("defs"), "get", a(e, "iface"))),
            e.let("hits", e.list_new(lt(e, "imember"))),
            e.foreach(
                e.call_m(e.v("def"), "members", e.tup()),
                "m",
                e.if_only(
                    and_b(
                        e,
                        e.eq(e.call_m(e.v("m"), "name", e.tup()), a(e, "member")),
                        e.eq(e.call_m(e.v("m"), "kind", e.tup()), a(e, "kind")),
                    ),
                    push(e, e.v("hits"), e.v("m")),
                ),
            ),
            count_let(e, "nh"),
            count_loop(e, "nh", e.v("hits")),
            e.let("count", e.fld(e.v("nh"), "v")),
            e.if_only(
                e.eq(e.v("count"), num(e, 0)),
                e.seq(
                    e.if_only(e.eq(e.call_m(e.v("def"), "parent", e.tup()), e.s("")), ret_m(e, e.v("none"))),
                    ret_m(
                        e,
                        hf(
                            e,
                            "h_find",
                            e.rec(
                                e.p("table", a(e, "table")),
                                e.p("iface", e.call_m(e.v("def"), "parent", e.tup())),
                                e.p("member", a(e, "member")),
                                e.p("kind", a(e, "kind")),
                                e.p("index", a(e, "index")),
                            ),
                        ),
                    ),
                ),
            ),
            e.let(
                "want",
                e.if_else(
                    and_b(e, e.mb.operator_lt(a(e, "index"), num(e, 0)), e.eq(e.v("count"), num(e, 1))),
                    e.int_of(0),
                    a(e, "index"),
                ),
            ),
            e.let("i", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                e.v("hits"),
                "h",
                e.seq(
                    e.if_only(
                        e.eq(e.fld(e.v("i"), "v"), e.v("want")),
                        ret_m(e, _ifound(e, e.b(True), a(e, "iface"), e.v("h"), e.v("count"))),
                    ),
                    e.incr(e.fld(e.v("i"), "v")),
                ),
            ),
            e.ret(_ifound(e, e.b(False), a(e, "iface"), _no_member(e), e.v("count"))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_number",
        body(
            e,
            e.let(
                "st",
                e.rec(
                    e.p("v", e.mb.as_(e.n(0), e.types_double())),
                    e.p("neg", e.int_of(0)),
                    e.p("hex", e.int_of(0)),
                    e.p("i", e.int_of(0)),
                ),
            ),
            e.foreach(
                e.call(e.mb.eval_str_utf8(), e.v("arg")),
                "b",
                e.seq(
                    e.let("n", e.mb.as_(e.v("b"), int_t(e))),
                    e.let("i", e.fld(e.v("st"), "i")),
                    e.let(
                        "digit",
                        e.if_else(
                            _in_range(e, e.v("n"), "0", "9"),
                            e.mb.operator_sub(e.v("n"), e.int_of(ord("0"))),
                            e.if_else(
                                _in_range(e, e.v("n"), "a", "f"),
                                e.mb.operator_sub(e.v("n"), e.int_of(ord("a") - 10)),
                                e.if_else(
                                    _in_range(e, e.v("n"), "A", "F"),
                                    e.mb.operator_sub(e.v("n"), e.int_of(ord("A") - 10)),
                                    e.int_of(-1),
                                ),
                            ),
                        ),
                    ),
                    e.if_else(
                        and_b(e, e.eq(e.v("i"), num(e, 0)), _byte_is(e, e.v("n"), "-")),
                        e.mb.set(e.fld(e.v("st"), "neg"), e.int_of(1)),
                        e.if_else(
                            and_b(
                                e,
                                e.eq(e.v("i"), num(e, 1)),
                                or_b(e, _byte_is(e, e.v("n"), "x"), _byte_is(e, e.v("n"), "X")),
                            ),
                            e.mb.set(e.fld(e.v("st"), "hex"), e.int_of(1)),
                            e.if_else(
                                or_b(
                                    e,
                                    e.mb.operator_lt(e.v("digit"), num(e, 0)),
                                    and_b(
                                        e,
                                        e.eq(e.fld(e.v("st"), "hex"), num(e, 0)),
                                        e.mb.operator_gt(e.v("digit"), num(e, 9)),
                                    ),
                                ),
                                e.mb.panic(e.cat(e.s("webidl: malformed number "), e.v("arg"))),
                                e.mb.set(
                                    e.fld(e.v("st"), "v"),
                                    e.mb.operator_add(
                                        e.mb.operator_mul(
                                            e.fld(e.v("st"), "v"),
                                            e.if_else(
                                                e.eq(e.fld(e.v("st"), "hex"), num(e, 1)),
                                                e.mb.as_(e.n(16), e.types_double()),
                                                e.mb.as_(e.n(10), e.types_double()),
                                            ),
                                        ),
                                        e.mb.as_(e.v("digit"), e.types_double()),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.incr(e.fld(e.v("st"), "i")),
                ),
            ),
            e.ret(
                e.if_else(
                    e.eq(e.fld(e.v("st"), "neg"), num(e, 1)),
                    e.mb.operator_sub(e.mb.as_(e.n(0), e.types_double()), e.fld(e.v("st"), "v")),
                    e.fld(e.v("st"), "v"),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_const_value",
        body(
            e,
            e.let(
                "f",
                hf(
                    e,
                    "h_find",
                    e.rec(
                        e.p("table", a(e, "table")),
                        e.p("iface", a(e, "iface")),
                        e.p("member", a(e, "member")),
                        e.p("kind", e.s("const")),
                        e.p("index", e.int_of(-1)),
                    ),
                ),
            ),
            e.if_only(
                e.not_(e.call_m(e.v("f"), "found", e.tup())),
                e.mb.panic(e.cat(e.s("webidl: no const "), a(e, "member"), e.s(" on "), a(e, "iface"))),
            ),
            e.ret(hf(e, "h_number", e.call_m(e.call_m(e.v("f"), "member", e.tup()), "value", e.tup()))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_split_overload",
        body(
            e,
            e.let(
                "st",
                e.rec(
                    e.p("hash", e.int_of(0)),
                    e.p("a", e.list_new(e.mb.types_byte())),
                    e.p("b", e.list_new(e.mb.types_byte())),
                ),
            ),
            e.foreach(
                e.call(e.mb.eval_str_utf8(), e.v("arg")),
                "b",
                e.if_else(
                    and_b(e, e.eq(e.fld(e.v("st"), "hash"), num(e, 0)), _byte_is(e, e.mb.as_(e.v("b"), int_t(e)), "#")),
                    e.mb.set(e.fld(e.v("st"), "hash"), e.int_of(1)),
                    e.if_else(
                        e.eq(e.fld(e.v("st"), "hash"), num(e, 0)),
                        push(e, e.fld(e.v("st"), "a"), e.v("b")),
                        push(e, e.fld(e.v("st"), "b"), e.v("b")),
                    ),
                ),
            ),
            e.if_only(
                e.eq(e.fld(e.v("st"), "hash"), num(e, 0)),
                ret_m(e, e.rec(e.p("base", e.v("arg")), e.p("index", e.int_of(-1)))),
            ),
            e.ret(
                e.rec(
                    e.p("base", _utf8(e, e.fld(e.v("st"), "a"))),
                    e.p("index", e.mb.as_(hf(e, "h_number", _utf8(e, e.fld(e.v("st"), "b"))), int_t(e))),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_sig",
        body(
            e,
            e.let("args", e.list_new(lt(e, "iparam"))),
            e.let("sp", hf(e, "h_split_overload", a(e, "member"))),
            e.let(
                "st",
                e.rec(
                    e.p("ok", e.int_of(1)),
                    e.p("err", e.dstr("")),
                    e.p("iface", a(e, "iface")),
                    e.p("member", a(e, "member")),
                    e.p("base", e.fld(e.v("sp"), "base")),
                    e.p("self", e.int_of(0)),
                    e.p("ret_out", e.int_of(0)),
                    e.p("ret_kind", e.dstr("void")),
                    e.p("ret_iface", e.dstr("")),
                ),
            ),
            e.if_only(
                e.eq(a(e, "kind"), e.s("global")),
                e.seq(
                    e.mb.set(e.fld(e.v("st"), "ret_kind"), e.dstr("handle")),
                    e.mb.set(e.fld(e.v("st"), "ret_iface"), e.dstr("Window")),
                    ret_m(e, _sig_of(e)),
                ),
            ),
            e.if_only(
                e.eq(a(e, "kind"), e.s("callback")),
                e.seq(
                    e.mb.set(e.fld(e.v("st"), "ret_kind"), e.dstr("handle")),
                    push(
                        e,
                        e.v("args"),
                        mk(
                            e,
                            "iparam",
                            e.p("optional", e.b(False)),
                            e.p("nullable", e.b(False)),
                            e.p("kind", e.dstr("str")),
                            e.p("iface", e.dstr("")),
                        ),
                    ),
                    ret_m(e, _sig_of(e)),
                ),
            ),
            e.if_only(
                e.eq(a(e, "kind"), e.s("ctor")),
                e.seq(
                    e.mb.set(e.fld(e.v("st"), "member"), e.dstr("constructor")),
                    e.mb.set(e.fld(e.v("st"), "base"), e.dstr("constructor")),
                ),
            ),
            e.let(
                "mkind",
                e.if_else(
                    e.eq(a(e, "kind"), e.s("op")),
                    e.dstr("op"),
                    e.if_else(e.eq(a(e, "kind"), e.s("ctor")), e.dstr("ctor"), e.dstr("attr")),
                ),
            ),
            e.let(
                "f",
                hf(
                    e,
                    "h_find",
                    e.rec(
                        e.p("table", a(e, "table")),
                        e.p("iface", a(e, "iface")),
                        e.p("member", e.fld(e.v("st"), "base")),
                        e.p("kind", e.v("mkind")),
                        e.p("index", e.fld(e.v("sp"), "index")),
                    ),
                ),
            ),
            e.if_only(
                and_b(
                    e,
                    e.not_(e.call_m(e.v("f"), "found", e.tup())),
                    e.mb.operator_gt(e.call_m(e.v("f"), "count", e.tup()), num(e, 1)),
                ),
                _sig_err(
                    e,
                    e.cat(
                        to_str(e, e.call_m(e.v("f"), "count", e.tup())),
                        e.s(" overloads of "),
                        e.fld(e.v("st"), "base"),
                        e.s(" on "),
                        e.call_m(e.v("f"), "iface", e.tup()),
                        e.s("; select one as "),
                        e.fld(e.v("st"), "base"),
                        e.s("#<index> (declaration order from 0)"),
                    ),
                ),
            ),
            e.if_only(
                e.not_(e.call_m(e.v("f"), "found", e.tup())),
                _sig_err(
                    e,
                    e.cat(e.s("no "), e.v("mkind"), e.s(" "), e.fld(e.v("st"), "member"), e.s(" on "), a(e, "iface")),
                ),
            ),
            e.mb.set(e.fld(e.v("st"), "iface"), e.call_m(e.v("f"), "iface", e.tup())),
            e.let("m", e.call_m(e.v("f"), "member", e.tup())),
            e.if_only(
                and_b(e, e.eq(a(e, "kind"), e.s("set")), e.call_m(e.v("m"), "readonly", e.tup())),
                _sig_err(e, e.cat(e.s("readonly attribute "), e.fld(e.v("st"), "member"))),
            ),
            e.if_only(
                e.not_(or_b(e, e.eq(a(e, "kind"), e.s("ctor")), e.call_m(e.v("m"), "static_", e.tup()))),
                e.mb.set(e.fld(e.v("st"), "self"), e.int_of(1)),
            ),
            e.if_only(
                or_b(e, e.eq(a(e, "kind"), e.s("op")), e.eq(a(e, "kind"), e.s("ctor"))),
                e.foreach(
                    e.call_m(e.v("m"), "args", e.tup()),
                    "ar",
                    e.seq(
                        e.if_only(
                            e.call_m(e.v("ar"), "variadic", e.tup()),
                            _sig_err(
                                e,
                                e.cat(
                                    e.s("variadic argument "),
                                    e.call_m(e.v("ar"), "name", e.tup()),
                                    e.s(" is not supported"),
                                ),
                            ),
                        ),
                        push(
                            e,
                            e.v("args"),
                            hf(
                                e,
                                "h_param",
                                e.rec(
                                    e.p("table", a(e, "table")),
                                    e.p("ty", e.call_m(e.v("ar"), "ty", e.tup())),
                                    e.p("optional", e.call_m(e.v("ar"), "optional", e.tup())),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            e.if_only(
                e.eq(a(e, "kind"), e.s("set")),
                push(
                    e,
                    e.v("args"),
                    hf(
                        e,
                        "h_param",
                        e.rec(
                            e.p("table", a(e, "table")),
                            e.p("ty", e.call_m(e.v("m"), "ty", e.tup())),
                            e.p("optional", e.b(False)),
                        ),
                    ),
                ),
            ),
            e.if_only(
                e.eq(a(e, "kind"), e.s("ctor")),
                e.seq(
                    e.mb.set(e.fld(e.v("st"), "ret_kind"), e.dstr("handle")),
                    e.mb.set(e.fld(e.v("st"), "ret_iface"), a(e, "iface")),
                ),
            ),
            e.if_only(
                or_b(e, e.eq(a(e, "kind"), e.s("op")), e.eq(a(e, "kind"), e.s("get"))),
                e.seq(
                    e.let(
                        "ar",
                        hf(
                            e,
                            "h_abi_ret",
                            e.rec(e.p("table", a(e, "table")), e.p("ty", e.call_m(e.v("m"), "ty", e.tup()))),
                        ),
                    ),
                    e.if_only(e.fld(e.v("ar"), "out"), e.mb.set(e.fld(e.v("st"), "ret_out"), e.int_of(1))),
                    e.mb.set(e.fld(e.v("st"), "ret_kind"), e.fld(e.v("ar"), "kind")),
                    e.mb.set(e.fld(e.v("st"), "ret_iface"), e.fld(e.v("ar"), "iface")),
                ),
            ),
            e.if_only(
                e.eq(e.fld(e.v("st"), "ret_kind"), e.s("buf")),
                _sig_err(e, e.cat(e.s("buffer-typed return of "), e.fld(e.v("st"), "base"))),
            ),
            e.ret(_sig_of(e)),
        ),
    )
    fn_impl(
        e,
        x,
        "h_sig_name",
        body(
            e,
            e.if_only(e.eq(a(e, "name"), e.s("global")), ret_m(e, _sig_call(e, e.dstr(""), e.dstr(""), "global"))),
            e.if_only(e.eq(a(e, "name"), e.s("callback")), ret_m(e, _sig_call(e, e.dstr(""), e.dstr(""), "callback"))),
            e.let(
                "st",
                e.rec(
                    e.p("dot", e.int_of(0)),
                    e.p("a", e.list_new(e.mb.types_byte())),
                    e.p("b", e.list_new(e.mb.types_byte())),
                    e.p("nb", e.int_of(0)),
                    e.p("last", e.int_of(0)),
                ),
            ),
            e.foreach(
                e.call(e.mb.eval_str_utf8(), a(e, "name")),
                "b",
                e.seq(
                    e.let("n", e.mb.as_(e.v("b"), int_t(e))),
                    e.if_else(
                        and_b(e, e.eq(e.fld(e.v("st"), "dot"), num(e, 0)), _byte_is(e, e.v("n"), ".")),
                        e.mb.set(e.fld(e.v("st"), "dot"), e.int_of(1)),
                        e.if_else(
                            e.eq(e.fld(e.v("st"), "dot"), num(e, 0)),
                            push(e, e.fld(e.v("st"), "a"), e.v("b")),
                            e.seq(
                                push(e, e.fld(e.v("st"), "b"), e.v("b")),
                                e.incr(e.fld(e.v("st"), "nb")),
                                e.mb.set(e.fld(e.v("st"), "last"), e.v("n")),
                            ),
                        ),
                    ),
                ),
            ),
            e.if_only(
                e.eq(e.fld(e.v("st"), "dot"), num(e, 0)),
                e.mb.panic(e.cat(e.s("webidl: malformed import name "), a(e, "name"))),
            ),
            e.let("set", _byte_is(e, e.fld(e.v("st"), "last"), "=")),
            e.let("mb", e.list_new(e.mb.types_byte())),
            e.let("i", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                e.fld(e.v("st"), "b"),
                "b",
                e.seq(
                    e.if_only(
                        or_b(
                            e,
                            e.not_(e.v("set")),
                            e.mb.operator_lt(
                                e.fld(e.v("i"), "v"), e.mb.operator_sub(e.fld(e.v("st"), "nb"), num(e, 1))
                            ),
                        ),
                        push(e, e.v("mb"), e.v("b")),
                    ),
                    e.incr(e.fld(e.v("i"), "v")),
                ),
            ),
            e.let("iface", _utf8(e, e.fld(e.v("st"), "a"))),
            e.let("member", _utf8(e, e.v("mb"))),
            e.if_only(e.v("set"), ret_m(e, _sig_call(e, e.v("iface"), e.v("member"), "set"))),
            e.if_only(
                e.eq(e.v("member"), e.s("constructor")), ret_m(e, _sig_call(e, e.v("iface"), e.v("member"), "ctor"))
            ),
            e.let("op", _sig_call(e, e.v("iface"), e.v("member"), "op")),
            e.if_only(e.call_m(e.v("op"), "ok", e.tup()), ret_m(e, e.v("op"))),
            e.ret(_sig_call(e, e.v("iface"), e.v("member"), "get")),
        ),
    )
    fn_impl(
        e,
        x,
        "h_mangle",
        body(
            e,
            e.ret(
                e.cat(
                    a(e, "iface"),
                    e.s("."),
                    a(e, "member"),
                    e.if_else(e.eq(a(e, "kind"), e.s("set")), e.dstr("="), e.dstr("")),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_table",
        body(
            e,
            e.let("defs", e.map_new(str_(e), lt(e, "idef"))),
            e.let("typedefs", e.map_new(str_(e), lt(e, "itype"))),
            e.let("kind", e.rec(e.p("v", e.dstr("")))),
            e.foreach(
                e.v("arg"),
                "d0",
                e.seq(
                    e.mb.set(e.fld(e.v("kind"), "v"), e.call_m(e.v("d0"), "kind", e.tup())),
                    e.if_only(
                        e.eq(e.fld(e.v("kind"), "v"), e.s("typedef")),
                        e.call_m(
                            e.v("typedefs"),
                            "put",
                            e.tup(e.call_m(e.v("d0"), "name", e.tup()), e.call_m(e.v("d0"), "ty", e.tup())),
                        ),
                    ),
                    e.if_only(
                        and_b(
                            e,
                            e.not_(e.eq(e.fld(e.v("kind"), "v"), e.s("typedef"))),
                            and_b(
                                e,
                                e.not_(e.eq(e.fld(e.v("kind"), "v"), e.s("includes"))),
                                e.not_(e.call_m(e.v("d0"), "partial", e.tup())),
                            ),
                        ),
                        e.call_m(e.v("defs"), "put", e.tup(e.call_m(e.v("d0"), "name", e.tup()), e.v("d0"))),
                    ),
                ),
            ),
            e.foreach(
                e.v("arg"),
                "d1",
                e.if_only(
                    and_b(
                        e,
                        e.call_m(e.v("d1"), "partial", e.tup()),
                        hf(
                            e,
                            "h_has",
                            e.rec(e.p("defs", e.v("defs")), e.p("name", e.call_m(e.v("d1"), "name", e.tup()))),
                        ),
                    ),
                    e.foreach(
                        e.call_m(e.v("d1"), "members", e.tup()),
                        "m",
                        push(
                            e,
                            e.call_m(
                                e.call_m(e.v("defs"), "get", e.call_m(e.v("d1"), "name", e.tup())), "members", e.tup()
                            ),
                            e.v("m"),
                        ),
                    ),
                ),
            ),
            e.foreach(
                e.v("arg"),
                "d2",
                e.if_only(
                    and_b(
                        e,
                        e.eq(e.call_m(e.v("d2"), "kind", e.tup()), e.s("includes")),
                        and_b(
                            e,
                            hf(
                                e,
                                "h_has",
                                e.rec(e.p("defs", e.v("defs")), e.p("name", e.call_m(e.v("d2"), "name", e.tup()))),
                            ),
                            hf(
                                e,
                                "h_has",
                                e.rec(e.p("defs", e.v("defs")), e.p("name", e.call_m(e.v("d2"), "parent", e.tup()))),
                            ),
                        ),
                    ),
                    e.foreach(
                        e.call_m(
                            e.call_m(e.v("defs"), "get", e.call_m(e.v("d2"), "parent", e.tup())), "members", e.tup()
                        ),
                        "m",
                        push(
                            e,
                            e.call_m(
                                e.call_m(e.v("defs"), "get", e.call_m(e.v("d2"), "name", e.tup())), "members", e.tup()
                            ),
                            e.v("m"),
                        ),
                    ),
                ),
            ),
            e.ret(mk(e, "itable", e.p("defs", e.v("defs")), e.p("typedefs", e.v("typedefs")))),
        ),
    )

    x.append(e.finish(e.v("d")))
    defs = []
    defs.append(e.p("parse", e.v("h_parse")))
    defs.append(e.p("table", e.v("h_table")))
    for fn in ["has", "resolve", "kind", "abi_ret", "find", "mangle", "sig", "sig_name", "const_value", "ancestor"]:
        defs.append(e.p(fn, e.v("h_" + fn)))
    for obj in ["itype", "iarg", "imember", "idef", "itable", "ifound", "iparam", "isig"]:
        defs.append(e.p(obj + "_t", t(e, obj)))
    x.append(e.ret(e.rec(*defs)))

    y = []
    y.append(e.let("k", e.lower(e.mb.seq(x))))
    texts = []
    for file in SPEC_FILES:
        texts.append(
            e.seq(
                e.let("f", e.fld(e.import_git("w", SPEC_REPO, SPEC_COMMIT), "ed", "idl", file)),
                e.ret(
                    _utf8(
                        e,
                        e.mb.as_(
                            e.call_m(
                                e.v("f"), "read", e.rec(e.p("offset", e.int_of(0)), e.p("len", e.fld(e.v("f"), "len")))
                            ),
                            e.list_type(e.mb.types_byte()),
                        ),
                    )
                ),
            )
        )
        texts.append(e.s("\n"))
    y.append(e.let("text", e.cat(*texts)))
    y.append(e.let("spec_defs", e.call(e.fld(e.v("k"), "parse"), e.v("text"))))
    y.append(e.let("spec", e.call(e.fld(e.v("k"), "table"), e.v("spec_defs"))))
    names = [
        "parse",
        "table",
        "has",
        "resolve",
        "kind",
        "abi_ret",
        "find",
        "mangle",
        "sig",
        "sig_name",
        "const_value",
        "ancestor",
        "itype_t",
        "iarg_t",
        "imember_t",
        "idef_t",
        "itable_t",
        "ifound_t",
        "iparam_t",
        "isig_t",
    ]
    ydefs = []
    for name in names:
        ydefs.append(e.p(name, e.fld(e.v("k"), name)))
    ydefs.append(e.p("spec_defs", e.v("spec_defs")))
    ydefs.append(e.p("spec", e.v("spec")))
    y.append(e.ret(e.rec(*ydefs)))

    top = []
    top.append(e.let("s", e.lower(e.mb.seq(y))))
    exports = []
    for name in names:
        exports.append(e.p(name, e.fld(e.v("s"), name)))
    exports.append(e.p("spec_defs", e.fld(e.v("s"), "spec_defs")))
    exports.append(e.p("spec", e.fld(e.v("s"), "spec")))
    top.append(e.ret(e.rec(*exports)))
    return top
