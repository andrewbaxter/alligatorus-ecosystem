"""wasi-0.1.atz: WASI preview1 function types, derived from the upstream witx spec.

Exports `module`, the import module name, and one field per function of the spec, `<name>_t`, its wasm
function type (a constant: an app passes `wasi.fd_write_t` to `import_fn` directly). The spec is parsed when
this module is built, and the export record is built from the parsed names by a const function, with the
compiler's expression constructors.
"""

from ..eco_mb import p
from ..target_mb import (
    a,
    accessor,
    and_b,
    body,
    bool_t,
    const_fn,
    count_let,
    count_loop,
    cve_has,
    cve_value,
    def_obj,
    dfalse,
    err_cve,
    fn_def,
    fn_impl,
    hf,
    hf_rec,
    int_t,
    loc,
    lt,
    mk,
    num,
    or_b,
    push,
    ret_m,
    str_,
    t,
    to_str,
    ty,
    voc_t,
    xx,
)

MODULE = "wasi_snapshot_preview1"

SPEC_REPO = "https://github.com/WebAssembly/WASI"

SPEC_COMMIT = "fae981bae14809d91f9bc2d63852d461f331d161"


def _fn_def(e, out, name, arg_type, ret):
    return fn_def(e, out, "wasi", name, arg_type, ret)


def _fn_impl_void(e, out, name, body_expr):
    sig = e.fn_sigs.pop(name)
    out.append(e.func_impl(e.v(name + "_b"), sig[0], e.option_type_none(), sig[2], e.stage(body_expr)))


def _sx_t(e):
    return t(e, "sx")


def _types_t(e):
    return e.map_type(str_(e), t(e, "wt"))


def _byte_is(e, b, c):
    return e.eq(e.mb.as_(b, int_t(e)), num(e, ord(c)))


def _atom_of(e, node):
    return e.call_m(node, "atom", e.tup())


def _kids_of(e, node):
    return e.call_m(node, "kids", e.tup())


def _kid(e, node, i):
    """`i`: expr or int literal."""
    if isinstance(i, int):
        i = e.int_of(i)
    return hf_rec(e, "h_kid", p("node", node), p("i", i))


def _head(e, node):
    return hf(e, "h_head", node)


def _is_ref(e, atom):
    return hf(e, "h_is_ref", atom)


def _wasm_field(e, name):
    return e.fld(e.lower_v("wasm"), name)


def _wasm_type(e, name):
    return e.mb.as_(_wasm_field(e, name), ty(e))


def _ptr_of(e, pointee):
    return e.call(_wasm_field(e, "ptr"), pointee)


def _value_type(e, node):
    return hf_rec(e, "h_value_type", p("types", a(e, "types")), p("node", node))


def _kind_of(e, wt):
    return e.call_m(wt, "kind", e.tup())


def _new_node(e, atom):
    return mk(e, "sx", p("atom", atom), p("kids", e.list_new(lt(e, "sx"))))


def _put_type(e, types, name, kind, repr_, elem):
    return e.call_m(types, "put", e.tup(name, mk(e, "wt", p("kind", kind), p("repr", repr_), p("elem", elem))))


def _spec_text(e, file):
    return e.seq(
        e.let("f", e.fld(e.import_git("w", SPEC_REPO, SPEC_COMMIT), "preview1", "witx", file)),
        e.ret(
            _utf8(
                e,
                e.mb.as_(
                    e.call_m(e.v("f"), "read", e.rec(p("offset", e.int_of(0)), p("len", e.fld(e.v("f"), "len")))),
                    e.list_type(e.mb.types_byte()),
                ),
            )
        ),
    )


def _utf8(e, bytes_):
    return e.match_of(
        e.call(e.eval_builtin("str_from_utf8"), bytes_),
        "__s",
        None,
        p("some", e.v("__s")),
        p("none", e.mb.panic(e.s("witx: spec text is not valid UTF-8"))),
    )


def _stack_top(e):
    return e.call_m(e.v("stack"), "get", to_str(e, e.fld(e.v("st"), "depth")))


def _set_st(e, field, value):
    return e.mb.set(e.fld(e.v("st"), field), value)


def _st_is(e, field, value):
    return e.eq(e.fld(e.v("st"), field), num(e, value))


def _entry(e, key, value):
    return e.call(e.eval_builtin("expr_record_entry"), e.rec(p("key", key), p("value", value)))


def _exports_const_fn(e, x):
    """`wasi.exports fns`: the module's export record, `module` and `<name>_t` for each function in the parsed map
    `fns` (a constant `map(str, type)`), built as a record expression and evaluated in the caller's context."""
    parts = [
        e.let("argv", a(e, "argument")),
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), "wasi.exports: argument has no value"))),
        e.let("host", e.fld(e.call(e.mb.must_reinterpret(), e.tup(cve_value(e, e.v("argv")), voc_t(e))), "data")),
        e.let("fns", e.call(e.mb.must_reinterpret(), e.tup(e.v("host"), e.map_type(str_(e), ty(e))))),
        e.let("entries", e.list_new(e.mb.builtin("types", "expr_record_entry"))),
        push(e, e.v("entries"), _entry(e, e.stage(e.s("module")), e.stage(e.s(MODULE)))),
        e.foreach(
            e.v("fns"),
            "fn",
            push(
                e,
                e.v("entries"),
                _entry(
                    e,
                    e.stage(e.lower(e.cat(e.fld(e.v("fn"), "key"), e.s("_t")))),
                    e.stage(e.lower(e.fld(e.v("fn"), "value"))),
                ),
            ),
        ),
        e.ret(
            e.call(
                e.eval_builtin("const_eval"),
                e.rec(
                    p("xx", xx(e)),
                    p("loc", loc(e)),
                    p(
                        "staged",
                        e.call(e.eval_builtin("expr_record"), e.rec(p("loc", loc(e)), p("entries", e.v("entries")))),
                    ),
                ),
            )
        ),
    ]
    const_fn(e, x, "exports_b", "wasi.exports", body(e, *parts))


def module(e):
    x = []
    x.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    def_obj(e, x, "sx", "witx s-expression", e.rec(p("atom", str_(e)), p("kids", e.list_type(_sx_t(e)))))
    accessor(e, x, "sx", "atom", str_(e))
    accessor(e, x, "sx", "kids", e.list_type(_sx_t(e)))
    def_obj(e, x, "wt", "witx type", e.rec(p("kind", str_(e)), p("repr", str_(e)), p("elem", str_(e))))
    accessor(e, x, "wt", "kind", str_(e))
    accessor(e, x, "wt", "repr", str_(e))
    accessor(e, x, "wt", "elem", str_(e))

    _fn_def(e, x, "h_kid", e.rec(p("node", _sx_t(e)), p("i", int_t(e))), _sx_t(e))
    fn_impl(
        e,
        x,
        "h_kid",
        body(
            e,
            e.let("k", e.rec(p("i", e.int_of(0)))),
            e.foreach(
                _kids_of(e, a(e, "node")),
                "c",
                e.seq(
                    e.if_only(e.eq(e.fld(e.v("k"), "i"), a(e, "i")), ret_m(e, e.v("c"))),
                    e.incr(e.fld(e.v("k"), "i")),
                ),
            ),
            e.mb.panic(
                e.cat(e.s("witx: node "), _atom_of(e, a(e, "node")), e.s(" has no child "), to_str(e, a(e, "i")))
            ),
        ),
    )
    _fn_def(e, x, "h_head", _sx_t(e), str_(e))
    fn_impl(
        e,
        x,
        "h_head",
        body(e, e.foreach(_kids_of(e, e.v("arg")), "c", ret_m(e, _atom_of(e, e.v("c")))), e.ret(e.dstr(""))),
    )
    _fn_def(e, x, "h_is_ref", str_(e), bool_t(e))
    fn_impl(
        e,
        x,
        "h_is_ref",
        body(
            e,
            e.foreach(e.call(e.mb.eval_str_utf8(), e.v("arg")), "b", ret_m(e, _byte_is(e, e.v("b"), "$"))),
            e.ret(dfalse(e)),
        ),
    )

    _fn_def(e, x, "h_parse", str_(e), _sx_t(e))

    def flush():
        return e.if_only(
            e.mb.operator_gt(e.fld(e.v("st"), "n"), num(e, 0)),
            e.seq(
                push(e, _kids_of(e, _stack_top(e)), _new_node(e, _utf8(e, e.fld(e.v("st"), "tok")))),
                _set_st(e, "tok", e.list_new(e.mb.types_byte())),
                _set_st(e, "n", e.int_of(0)),
            ),
        )

    def push_byte():
        return e.seq(push(e, e.fld(e.v("st"), "tok"), e.v("b")), e.incr(e.fld(e.v("st"), "n")))

    on_open = e.seq(
        flush(),
        e.let("node", _new_node(e, e.dstr(""))),
        push(e, _kids_of(e, _stack_top(e)), e.v("node")),
        e.incr(e.fld(e.v("st"), "depth")),
        e.call_m(e.v("stack"), "put", e.tup(to_str(e, e.fld(e.v("st"), "depth")), e.v("node"))),
    )
    on_close = e.seq(
        flush(),
        e.if_only(_st_is(e, "depth", 0), e.mb.panic(e.s("witx: unbalanced ')'"))),
        _set_st(e, "depth", e.mb.operator_sub(e.fld(e.v("st"), "depth"), num(e, 1))),
    )
    is_space = or_b(
        e,
        _byte_is(e, e.v("b"), " "),
        or_b(e, _byte_is(e, e.v("b"), "\n"), or_b(e, _byte_is(e, e.v("b"), "\t"), _byte_is(e, e.v("b"), "\r"))),
    )
    plain = e.if_else(
        _byte_is(e, e.v("b"), ";"),
        e.seq(flush(), _set_st(e, "comment", e.int_of(1))),
        e.if_else(
            _byte_is(e, e.v("b"), '"'),
            e.seq(flush(), _set_st(e, "quoted", e.int_of(1)), e.incr(e.fld(e.v("st"), "n"))),
            e.if_else(
                _byte_is(e, e.v("b"), "("),
                on_open,
                e.if_else(_byte_is(e, e.v("b"), ")"), on_close, e.if_else(is_space, flush(), push_byte())),
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_parse",
        body(
            e,
            e.let("root", _new_node(e, e.dstr(""))),
            e.let("stack", e.map_new(str_(e), lt(e, "sx"))),
            e.call_m(e.v("stack"), "put", e.tup(e.s("0"), e.v("root"))),
            e.let(
                "st",
                e.rec(
                    p("depth", e.int_of(0)),
                    p("tok", e.list_new(e.mb.types_byte())),
                    p("n", e.int_of(0)),
                    p("comment", e.int_of(0)),
                    p("quoted", e.int_of(0)),
                ),
            ),
            e.foreach(
                e.call(e.mb.eval_str_utf8(), e.v("arg")),
                "b",
                e.if_else(
                    _st_is(e, "comment", 1),
                    e.if_only(_byte_is(e, e.v("b"), "\n"), _set_st(e, "comment", e.int_of(0))),
                    e.if_else(
                        _st_is(e, "quoted", 1),
                        e.if_else(
                            _byte_is(e, e.v("b"), '"'),
                            e.seq(_set_st(e, "quoted", e.int_of(0)), flush()),
                            push_byte(),
                        ),
                        plain,
                    ),
                ),
            ),
            flush(),
            e.if_only(e.not_(_st_is(e, "depth", 0)), e.mb.panic(e.s("witx: unbalanced '('"))),
            e.ret(e.v("root")),
        ),
    )

    _fn_def(e, x, "h_types", e.rec(p("root", _sx_t(e)), p("types", _types_t(e))), e.tup())

    def name():
        return _atom_of(e, _kid(e, e.v("n"), 1))

    def def_():
        return e.v("def")

    _fn_impl_void(
        e,
        x,
        "h_types",
        e.foreach(
            _kids_of(e, a(e, "root")),
            "n",
            e.if_only(
                e.eq(_head(e, e.v("n")), e.s("typename")),
                e.seq(
                    e.let("def", _kid(e, e.v("n"), 2)),
                    e.let("dh", _head(e, def_())),
                    e.if_else(
                        e.not_(e.eq(_atom_of(e, def_()), e.s(""))),
                        _put_type(e, a(e, "types"), name(), e.dstr("scalar"), _atom_of(e, def_()), e.dstr("")),
                        e.if_else(
                            e.eq(e.v("dh"), e.s("handle")),
                            _put_type(e, a(e, "types"), name(), e.dstr("handle"), e.dstr("i32"), e.dstr("")),
                            e.if_else(
                                or_b(e, e.eq(e.v("dh"), e.s("enum")), e.eq(e.v("dh"), e.s("flags"))),
                                _put_type(
                                    e,
                                    a(e, "types"),
                                    name(),
                                    e.v("dh"),
                                    _atom_of(e, _kid(e, _kid(e, def_(), 1), 2)),
                                    e.dstr(""),
                                ),
                                e.if_else(
                                    e.eq(e.v("dh"), e.s("list")),
                                    _put_type(
                                        e,
                                        a(e, "types"),
                                        name(),
                                        e.dstr("list"),
                                        e.dstr(""),
                                        _atom_of(e, _kid(e, def_(), 1)),
                                    ),
                                    e.if_else(
                                        or_b(e, e.eq(e.v("dh"), e.s("record")), e.eq(e.v("dh"), e.s("union"))),
                                        _put_type(e, a(e, "types"), name(), e.v("dh"), e.dstr(""), e.dstr("")),
                                        e.mb.panic(
                                            e.cat(
                                                e.s("witx: unsupported type definition "),
                                                e.v("dh"),
                                                e.s(" for "),
                                                name(),
                                            )
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    _fn_def(e, x, "h_scalar", str_(e), ty(e))
    cases = []
    for witx_name, wasm_name in [
        ("u8", "u8"),
        ("u16", "u16"),
        ("u32", "u32"),
        ("u64", "u64"),
        ("s8", "i8"),
        ("s16", "i16"),
        ("s32", "i32"),
        ("s64", "i64"),
        ("char", "u32"),
        ("f32", "f32"),
        ("f64", "f64"),
    ]:
        cases.append(e.if_only(e.eq(e.v("arg"), e.s(witx_name)), ret_m(e, _wasm_type(e, wasm_name))))
    cases.append(e.mb.panic(e.cat(e.s("witx: not a scalar type: "), e.v("arg"))))
    fn_impl(e, x, "h_scalar", body(e, *cases))
    _fn_def(e, x, "h_value_type", e.rec(p("types", _types_t(e)), p("node", _sx_t(e))), ty(e))
    fn_impl(
        e,
        x,
        "h_value_type",
        body(
            e,
            e.let("atom", _atom_of(e, a(e, "node"))),
            e.if_only(
                e.eq(e.v("atom"), e.s("")),
                e.seq(
                    e.let("form", _atom_of(e, _kid(e, a(e, "node"), 1))),
                    e.if_only(
                        e.not_(
                            and_b(
                                e,
                                e.eq(_head(e, a(e, "node")), e.s("@witx")),
                                or_b(e, e.eq(e.v("form"), e.s("pointer")), e.eq(e.v("form"), e.s("const_pointer"))),
                            )
                        ),
                        e.mb.panic(e.cat(e.s("witx: unsupported type form "), _head(e, a(e, "node")))),
                    ),
                    ret_m(e, _ptr_of(e, _value_type(e, _kid(e, a(e, "node"), 2)))),
                ),
            ),
            e.if_only(e.not_(_is_ref(e, e.v("atom"))), ret_m(e, hf(e, "h_scalar", e.v("atom")))),
            e.let("wt", e.call_m(a(e, "types"), "get", e.v("atom"))),
            e.let("kind", _kind_of(e, e.v("wt"))),
            e.if_only(e.eq(e.v("kind"), e.s("handle")), ret_m(e, _wasm_type(e, "i32"))),
            e.if_only(
                or_b(e, e.eq(e.v("kind"), e.s("record")), e.eq(e.v("kind"), e.s("union"))),
                ret_m(e, _wasm_type(e, "void")),
            ),
            e.if_only(
                e.eq(e.v("kind"), e.s("list")),
                e.mb.panic(e.cat(e.s("witx: list type used by value: "), e.v("atom"))),
            ),
            e.ret(hf(e, "h_scalar", e.call_m(e.v("wt"), "repr", e.tup()))),
        ),
    )
    _fn_def(
        e,
        x,
        "h_param",
        e.rec(p("types", _types_t(e)), p("node", _sx_t(e)), p("out", e.list_type(ty(e)))),
        e.tup(),
    )
    _fn_impl_void(
        e,
        x,
        "h_param",
        e.seq(
            e.let("tn", _kid(e, a(e, "node"), 2)),
            e.let("atom", _atom_of(e, e.v("tn"))),
            e.let(
                "is_list",
                and_b(
                    e,
                    _is_ref(e, e.v("atom")),
                    e.eq(_kind_of(e, e.call_m(a(e, "types"), "get", e.v("atom"))), e.s("list")),
                ),
            ),
            e.if_else(
                e.eq(e.v("atom"), e.s("string")),
                e.seq(
                    push(e, a(e, "out"), _ptr_of(e, _wasm_field(e, "u8"))),
                    push(e, a(e, "out"), _wasm_field(e, "u32")),
                ),
                e.if_else(
                    e.v("is_list"),
                    e.seq(
                        push(e, a(e, "out"), _ptr_of(e, _wasm_field(e, "void"))),
                        push(e, a(e, "out"), _wasm_field(e, "u32")),
                    ),
                    push(e, a(e, "out"), _value_type(e, e.v("tn"))),
                ),
            ),
        ),
    )
    _fn_def(
        e,
        x,
        "h_result",
        e.rec(p("types", _types_t(e)), p("node", _sx_t(e)), p("out", e.list_type(ty(e)))),
        ty(e),
    )
    fn_impl(
        e,
        x,
        "h_result",
        body(
            e,
            e.let("ex", _kid(e, a(e, "node"), 2)),
            e.if_only(
                e.not_(e.eq(_head(e, e.v("ex")), e.s("expected"))),
                e.mb.panic(e.cat(e.s("witx: unsupported result form "), _head(e, e.v("ex")))),
            ),
            count_let(e, "nk"),
            count_loop(e, "nk", _kids_of(e, e.v("ex"))),
            e.let("oks", e.list_new(lt(e, "sx"))),
            e.if_only(
                e.eq(e.fld(e.v("nk"), "v"), num(e, 3)),
                e.seq(
                    e.let("okn", _kid(e, e.v("ex"), 1)),
                    e.if_else(
                        e.eq(_head(e, e.v("okn")), e.s("tuple")),
                        e.seq(
                            e.let("ti", e.rec(p("i", e.int_of(0)))),
                            e.foreach(
                                _kids_of(e, e.v("okn")),
                                "tk",
                                e.seq(
                                    e.if_only(
                                        e.mb.operator_gt(e.fld(e.v("ti"), "i"), num(e, 0)),
                                        push(e, e.v("oks"), e.v("tk")),
                                    ),
                                    e.incr(e.fld(e.v("ti"), "i")),
                                ),
                            ),
                        ),
                        push(e, e.v("oks"), e.v("okn")),
                    ),
                ),
            ),
            e.foreach(e.v("oks"), "ok", push(e, a(e, "out"), _ptr_of(e, _value_type(e, e.v("ok"))))),
            e.let("errn", _kid(e, _kid(e, e.v("ex"), e.mb.operator_sub(e.fld(e.v("nk"), "v"), num(e, 1))), 1)),
            e.ret(_value_type(e, e.v("errn"))),
        ),
    )
    _fn_def(
        e,
        x,
        "h_fn_types",
        e.rec(p("root", _sx_t(e)), p("types", _types_t(e)), p("fns", e.map_type(str_(e), ty(e)))),
        e.tup(),
    )
    _fn_impl_void(
        e,
        x,
        "h_fn_types",
        e.foreach(
            _kids_of(e, a(e, "root")),
            "m",
            e.if_only(
                e.eq(_head(e, e.v("m")), e.s("module")),
                e.foreach(
                    _kids_of(e, e.v("m")),
                    "f",
                    e.if_only(
                        and_b(
                            e,
                            e.eq(_head(e, e.v("f")), e.s("@interface")),
                            e.eq(_atom_of(e, _kid(e, e.v("f"), 1)), e.s("func")),
                        ),
                        e.seq(
                            e.let("name", _atom_of(e, _kid(e, _kid(e, e.v("f"), 2), 1))),
                            e.let("params", e.list_new(ty(e))),
                            e.let("ret", e.rec(p("v", e.option_type_lowered_none()))),
                            e.foreach(
                                _kids_of(e, e.v("f")),
                                "p",
                                e.seq(
                                    e.if_only(
                                        e.eq(_head(e, e.v("p")), e.s("param")),
                                        hf_rec(
                                            e,
                                            "h_param",
                                            p("types", a(e, "types")),
                                            p("node", e.v("p")),
                                            p("out", e.v("params")),
                                        ),
                                    ),
                                    e.if_only(
                                        e.eq(_head(e, e.v("p")), e.s("result")),
                                        e.mb.set(
                                            e.fld(e.v("ret"), "v"),
                                            e.option_type_lowered_some(
                                                hf_rec(
                                                    e,
                                                    "h_result",
                                                    p("types", a(e, "types")),
                                                    p("node", e.v("p")),
                                                    p("out", e.v("params")),
                                                )
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                            e.call_m(
                                a(e, "fns"),
                                "put",
                                e.tup(
                                    e.v("name"),
                                    e.call(
                                        _wasm_field(e, "fn"),
                                        e.rec(
                                            p("params", e.v("params")),
                                            p(
                                                "ret",
                                                e.if_else(
                                                    e.fld(e.v("ret"), "v", "is_some"),
                                                    e.fld(e.v("ret"), "v", "value"),
                                                    _wasm_type(e, "void"),
                                                ),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    _exports_const_fn(e, x)
    x.append(e.finish(e.v("d")))
    x.append(
        e.ret(
            e.rec(
                p("parse", e.v("h_parse")),
                p("types", e.v("h_types")),
                p("fn_types", e.v("h_fn_types")),
                p("exports", e.fld(e.v("exports_b"), "func")),
                p("wt_t", t(e, "wt")),
            )
        )
    )

    y = []
    y.append(e.let("k", e.lower(e.mb.seq(x))))
    y.append(e.let("typenames", e.call(e.fld(e.v("k"), "parse"), _spec_text(e, "typenames.witx"))))
    y.append(e.let("preview1", e.call(e.fld(e.v("k"), "parse"), _spec_text(e, "wasi_snapshot_preview1.witx"))))
    y.append(e.let("types", e.map_new(str_(e), e.fld(e.v("k"), "wt_t"))))
    y.append(e.call(e.fld(e.v("k"), "types"), e.rec(p("root", e.v("typenames")), p("types", e.v("types")))))
    y.append(e.let("fns", e.map_new(str_(e), ty(e))))
    y.append(
        e.call(
            e.fld(e.v("k"), "fn_types"),
            e.rec(p("root", e.v("preview1")), p("types", e.v("types")), p("fns", e.v("fns"))),
        )
    )
    y.append(e.ret(e.rec(p("fns", e.v("fns")), p("exports", e.fld(e.v("k"), "exports")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(y))))
    top.append(e.ret(e.call(e.fld(e.v("k"), "exports"), e.fld(e.v("k"), "fns"))))
    return top
