"""webidl-wasm.atz: WebIDL binding hooks for the wat target (wasm imports from the `webidl` module)."""

from .eco_mb import p
from .target_mb import (
    a,
    acc,
    asp_id,
    asp_iface,
    bim,
    body,
    can_cast_from_self,
    cast_from_self,
    cast_to_panic,
    const_eval_in,
    cve_has,
    cve_t,
    cve_type,
    cve_value,
    def_iface,
    def_obj,
    dfalse,
    err_cve,
    errs_t,
    fn_def,
    fn_impl,
    fn_throws,
    graft,
    has,
    hf_rec,
    in_,
    int_t,
    is_runtime,
    loc,
    loc_t,
    lookup,
    lv,
    no_cast_to,
    num,
    ok_cve,
    or_b,
    push,
    ret_m,
    rt_bind_impl,
    rt_dispatch,
    rt_lift_impl,
    rt_use_impl,
    self_type,
    str_,
    t,
    tag_value,
    throw_err,
    try_er,
    ty,
    unwrap_cve_m,
    unwrap_cve_t,
    unwrap_m,
    xx,
    xx_t,
)
from .wat import bind_types

MODULE = "webidl"

KINDS = ["op", "get", "set", "ctor", "const"]


def _kind_of(kind):
    return KINDS.index(kind)


def _kind_is(e, kind):
    return e.eq(in_(e, "kind"), num(e, _kind_of(kind)))


def _kind_str(e):
    expr = e.dstr(KINDS[-1])
    for i in range(len(KINDS) - 2, -1, -1):
        expr = e.if_else(_kind_is(e, KINDS[i]), e.dstr(KINDS[i]), expr)
    return expr


def _webidl(e, fn):
    return e.lower(e.fld(e.v("webidl"), fn))


def module(e):
    x = []
    x.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    x.append(e.let("webidl", e.import_local("webidl", "webidl.atz")))
    bind_types(e, x)
    for t_ in ["i16", "u16"]:
        x.append(e.let("t_" + t_, e.fld(e.v("wasm"), t_)))
    x.append(e.let("t_pi32", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_i32"))))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    def_iface(e, x, "wop_m", p("kind", int_t(e)))
    def_obj(e, x, "wop_t", "webidl binding hook", e.rec(p("kind", int_t(e))))
    self_type(
        e,
        x,
        "wop_t",
        e.cat(e.s("webidl "), _kind_str(e)),
        rt_dispatch(e, str_(e), e.aspect_dispatch(lv(e, "wop_m_id"), asp_id(e, "function"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.if_only(e.not_(has(e, xx(e), a(e, "other"), "wop_m")), ret_m(e, dfalse(e))),
            e.ret(e.eq(in_(e, "kind"), acc(e, xx(e), a(e, "other"), "wop_m", "kind"))),
        ),
    )
    x.append(e.impl_interface(e.v("wop_t"), t(e, "wop_m"), p("kind", in_(e, "kind"))))
    rt_lift_impl(e, x, "wop_t")
    rt_bind_impl(e, x, "wop_t", str_(e))
    rt_use_impl(e, x, "wop_t")

    fn_def(e, x, "webidl", "h_str", e.rec(p("xx", xx_t(e)), p("loc", loc_t(e)), p("cv", cve_t(e))), str_(e))
    fn_throws(e, "h_str", errs_t(e))
    fn_impl(
        e,
        x,
        "h_str",
        body(
            e,
            e.let("c", unwrap_cve_t(e, const_eval_in(e, xx(e), e.stage(graft(e, a(e, "cv")))))),
            e.if_only(
                is_runtime(e, e.v("c")), throw_err(e, loc(e), "webidl: iface and member must be constant strings")
            ),
            e.let("sk", lookup(e, xx(e), cve_type(e, e.v("c")), e.mb.eval_aspect_string_const())),
            e.if_only(
                e.not_(e.fld(e.v("sk"), "is_some")), throw_err(e, loc(e), "webidl: iface and member must be strings")
            ),
            e.ret(bim(e, e.mb.eval_aspect_string_const(), "get", e.fld(e.v("sk"), "value"), cve_value(e, e.v("c")))),
        ),
    )

    wkinds_pairs = [
        ("flag", "t_i32"),
        ("handle", "t_i32"),
        ("ptr", "t_pu8"),
        ("len", "t_u32"),
        ("out", "t_pi32"),
        ("bool", "t_i32"),
        ("i8", "t_i8"),
        ("u8", "t_u8"),
        ("i16", "t_i16"),
        ("u16", "t_u16"),
        ("i32", "t_i32"),
        ("u32", "t_u32"),
        ("i64", "t_i64"),
        ("u64", "t_u64"),
        ("f32", "t_f32"),
        ("f64", "t_f64"),
    ]
    wkinds_entries = []
    for key, type_name in wkinds_pairs:
        wkinds_entries.append(p(key, e.lower_v(type_name)))
    wkinds = e.map_new(str_(e), ty(e), *wkinds_entries)
    wrets_pairs = [
        ("void", "t_void"),
        ("str", "t_i32"),
        ("handle", "t_i32"),
        ("bool", "t_i32"),
        ("i8", "t_i8"),
        ("u8", "t_u8"),
        ("i16", "t_i16"),
        ("u16", "t_u16"),
        ("i32", "t_i32"),
        ("u32", "t_u32"),
        ("i64", "t_i64"),
        ("u64", "t_u64"),
        ("f32", "t_f32"),
        ("f64", "t_f64"),
    ]
    wrets_entries = []
    for key, type_name in wrets_pairs:
        wrets_entries.append(p(key, e.lower_v(type_name)))
    wrets = e.map_new(str_(e), ty(e), *wrets_entries)
    x.append(
        e.impl_interface(
            e.v("wop_t"),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    e.let("kind", _kind_str(e)),
                    e.let("argv", a(e, "argument")),
                    e.if_only(
                        e.not_(cve_has(e, e.v("argv"))),
                        ret_m(e, err_cve(e, loc(e), "webidl: hook argument has no value")),
                    ),
                    e.let("rk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "record"))),
                    e.if_only(
                        e.not_(e.fld(e.v("rk"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "webidl: hook argument must be {iface, member}")),
                    ),
                    e.let(
                        "fields",
                        bim(
                            e,
                            asp_iface(e, "record"),
                            "take_fields",
                            e.fld(e.v("rk"), "value"),
                            e.rec(p("xx", xx(e)), p("loc", loc(e)), p("value", cve_value(e, e.v("argv")))),
                        ),
                    ),
                    e.let(
                        "iface",
                        unwrap_m(
                            e,
                            try_er(
                                e,
                                hf_rec(
                                    e,
                                    "h_str",
                                    p("xx", xx(e)),
                                    p("loc", loc(e)),
                                    p("cv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("iface")))),
                                ),
                                str_(e),
                            ),
                            cve_t(e),
                        ),
                    ),
                    e.let("mcell", e.rec(p("v", e.dstr("constructor")))),
                    e.if_only(
                        e.not_(_kind_is(e, "ctor")),
                        e.seq(
                            e.let(
                                "mname",
                                unwrap_m(
                                    e,
                                    try_er(
                                        e,
                                        hf_rec(
                                            e,
                                            "h_str",
                                            p("xx", xx(e)),
                                            p("loc", loc(e)),
                                            p("cv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("member")))),
                                        ),
                                        str_(e),
                                    ),
                                    cve_t(e),
                                ),
                            ),
                            e.mb.set(e.fld(e.v("mcell"), "v"), e.v("mname")),
                        ),
                    ),
                    e.let("member", e.fld(e.v("mcell"), "v")),
                    e.if_only(
                        _kind_is(e, "const"),
                        e.seq(
                            e.let(
                                "value",
                                e.call(
                                    _webidl(e, "const_value"),
                                    e.rec(
                                        p("table", e.lower(e.fld(e.v("webidl"), "spec"))),
                                        p("iface", e.v("iface")),
                                        p("member", e.v("member")),
                                    ),
                                ),
                            ),
                            ret_m(
                                e,
                                ok_cve(
                                    e,
                                    unwrap_cve_m(
                                        e, const_eval_in(e, xx(e), e.stage(e.lower(e.mb.as_(e.v("value"), int_t(e)))))
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.let(
                        "sig",
                        e.call(
                            _webidl(e, "sig"),
                            e.rec(
                                p("table", e.lower(e.fld(e.v("webidl"), "spec"))),
                                p("iface", e.v("iface")),
                                p("member", e.v("member")),
                                p("kind", e.v("kind")),
                            ),
                        ),
                    ),
                    e.if_only(
                        e.not_(e.call_m(e.v("sig"), "ok", e.tup())),
                        ret_m(e, err_cve(e, loc(e), e.cat(e.s("webidl: "), e.call_m(e.v("sig"), "err", e.tup())))),
                    ),
                    e.let("kinds", e.list_new(str_(e))),
                    e.if_only(e.call_m(e.v("sig"), "self", e.tup()), push(e, e.v("kinds"), e.dstr("handle"))),
                    e.foreach(
                        e.call_m(e.v("sig"), "args", e.tup()),
                        "ap",
                        e.seq(
                            e.if_only(e.call_m(e.v("ap"), "optional", e.tup()), push(e, e.v("kinds"), e.dstr("flag"))),
                            e.if_only(e.call_m(e.v("ap"), "nullable", e.tup()), push(e, e.v("kinds"), e.dstr("flag"))),
                            e.if_else(
                                or_b(
                                    e,
                                    e.eq(e.call_m(e.v("ap"), "kind", e.tup()), e.s("str")),
                                    e.eq(e.call_m(e.v("ap"), "kind", e.tup()), e.s("buf")),
                                ),
                                e.seq(push(e, e.v("kinds"), e.dstr("ptr")), push(e, e.v("kinds"), e.dstr("len"))),
                                push(e, e.v("kinds"), e.call_m(e.v("ap"), "kind", e.tup())),
                            ),
                        ),
                    ),
                    e.let("ret_out", e.call_m(e.v("sig"), "ret_out", e.tup())),
                    e.if_only(e.v("ret_out"), push(e, e.v("kinds"), e.dstr("out"))),
                    e.let("wkinds", wkinds),
                    e.let("wrets", wrets),
                    e.let("params", e.list_new(ty(e))),
                    e.foreach(e.v("kinds"), "k", push(e, e.v("params"), e.call_m(e.v("wkinds"), "get", e.v("k")))),
                    e.let(
                        "rkind", e.if_else(e.v("ret_out"), e.dstr("void"), e.call_m(e.v("sig"), "ret_kind", e.tup()))
                    ),
                    e.let("rty", e.call_m(e.v("wrets"), "get", e.v("rkind"))),
                    e.let(
                        "fnty",
                        e.call(
                            e.lower(e.fld(e.v("wasm"), "fn")), e.rec(p("params", e.v("params")), p("ret", e.v("rty")))
                        ),
                    ),
                    e.let(
                        "name",
                        e.call(
                            _webidl(e, "mangle"),
                            e.rec(
                                p("iface", e.call_m(e.v("sig"), "iface", e.tup())),
                                p("member", e.call_m(e.v("sig"), "member", e.tup())),
                                p("kind", e.v("kind")),
                            ),
                        ),
                    ),
                    e.let(
                        "ity",
                        e.call(
                            e.lower(e.fld(e.v("wasm"), "import_t")),
                            e.rec(p("module", e.s(MODULE)), p("name", e.v("name")), p("ty", e.v("fnty"))),
                        ),
                    ),
                    e.let(
                        "refcv",
                        unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(e.cat(e.s("$"), e.lower(e.v("name")))))),
                    ),
                    e.ret(tag_value(e, e.v("refcv"), e.v("ity"))),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )
    x.append(e.finish(e.v("d")))
    defs = []
    defs.append(p("wop_t_new", e.fld(e.v("wop_t"), "new")))
    defs.append(
        p(
            "global_t",
            e.call(e.fld(e.v("wasm"), "fn"), e.rec(p("params", e.list_new(e.mb.eval_type())), p("ret", e.v("t_i32")))),
        )
    )
    defs.append(
        p(
            "callback_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(
                    p("params", e.list_new(e.mb.eval_type(), e.v("t_pu8"), e.v("t_u32"))),
                    p("ret", e.v("t_i32")),
                ),
            ),
        )
    )
    x.append(e.ret(e.rec(*defs)))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    exports = []
    exports.append(p("module", e.s(MODULE)))
    for kind in KINDS:
        exports.append(
            p(kind, e.mb.as_(e.call(e.fld(e.v("k"), "wop_t_new"), e.rec(p("kind", e.int_of(_kind_of(kind))))), ty(e)))
        )
    for special in ["global", "callback"]:
        exports.append(
            p(
                special,
                e.call(
                    e.fld(e.v("wasm"), "import_fn"),
                    e.rec(p("module", e.s(MODULE)), p("name", e.s(special)), p("ty", e.fld(e.v("k"), special + "_t"))),
                ),
            )
        )
    top.append(e.ret(e.rec(*exports)))
    return top
