"""webidl-wasm.atz: WebIDL binding hooks for the wat target (wasm imports from the `webidl` module).

Handles are typed by interface: `handle(name)` yields `{raw, type, own}` for an interface name (`""` for any
handle: unions, mixins, callbacks and strings JS hands over as handles). `raw` is the handle as a plain value, an
i32 by representation that converts only to its ancestors in the spec's inheritance (`Element` passes where a
`Node` is expected, never the reverse: a downcast is the explicit `h as i32 as handle("X").raw`) and to i32; `type`
is destructor.atz's owned type over it, whose destroy function is the `webidl.release` import (webidl-js.atz frees
the table slot), and `own` its adopting type. A hook's parameters take the raw handle of their interface (a
borrowed use: an owned handle's binding converts through its reference); a hook returning a handle yields an owned
one of the returned interface, released when the binding holding it is dropped; a handle stored for the app's
lifetime is `.forget()`-ed into its cell. A hook whose result is nullable yields an option (option-wasm.atz) of the
result (an owned option over an owned handle or string handle, an option of the scalar otherwise), the import
returning the option's pair; it is read with `match`. A callback hook takes the callable's `(call, object)` pair
(closure-wasm.atz's `callback_of`), whose call function type must be the callback's signature behind the object
pointer, and yields the owned handle of the callback's name.
"""

from ..core import values
from ..memory import destructor
from ..eco_mb import p
from ..target_mb import (
    as_object,
    fn_of,
    cast_value,
    type_can_cast_from,
    cve_code,
    retag_values,
    bool_t,
    outer,
    lookup_v,
    has_b,
    handle_binds,
    handle_binding,
    type_aspect,
    is_equal,
    and_b,
    a,
    acc,
    asp_id,
    asp_iface,
    bim,
    body,
    call_result,
    can_cast_from_self,
    cast_from_self,
    cast_to_panic,
    code_none,
    const_eval_in,
    const_fn,
    count_let,
    count_loop,
    cv_of,
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
    mk,
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
from ..wasm.wat import bind_types

MODULE = "webidl"


KINDS = ["op", "get", "set", "ctor", "const", "callback", "intrinsic"]


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


def _raw_of(e, name):
    """In a hook's host code: the raw handle type of the interface `name` (an i32 by representation), carrying its
    ancestors' names (so the type needs no spec table where it is used)."""
    return e.mb.as_(
        mk(
            e,
            "wi_raw",
            p("name", name),
            p("under", e.lower(e.v("t_i32"))),
            p(
                "ancestors",
                e.call(_webidl(e, "ancestors"), e.rec(p("table", _webidl(e, "spec")), p("iface", name))),
            ),
        ),
        ty(e),
    )


def _handle_types(e, name):
    """In a hook's host code: `{type, own}` of the interface `name` (a host expression), destructor.atz's owned type
    over its raw handle type, destroyed by the release dependency (plain types: destructor.owned_of)."""
    return e.call(
        e.lower(e.fld(e.v("destructor"), "owned_of")),
        e.rec(p("under", _raw_of(e, name)), p("destroy", e.lower(e.v("release_dep")))),
    )


def _handle_fn(e, x):
    """`webidl.handle(name)`: a const function yielding the handle types of the interface `name`, `{raw, type,
    own}`: the raw handle type (one per name: any two are the same type), destructor.atz's owned type over it
    (destroyed by the release import) and its adopting type."""
    const_fn(
        e,
        x,
        "handle_b",
        "webidl.handle",
        body(
            e,
            e.let("argv", a(e, "argument")),
            e.if_only(
                e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), "webidl.handle: argument has no value"))
            ),
            e.if_only(
                e.not_(has_b(e, xx(e), cve_type(e, e.v("argv")), e.mb.eval_aspect_string_const())),
                ret_m(e, err_cve(e, loc(e), "webidl.handle: the interface name must be a constant string")),
            ),
            e.let(
                "name",
                bim(
                    e,
                    e.mb.eval_aspect_string_const(),
                    "get",
                    lookup_v(e, xx(e), cve_type(e, e.v("argv")), e.mb.eval_aspect_string_const()),
                    cve_value(e, e.v("argv")),
                ),
            ),
            e.let("raw", _raw_of(e, e.v("name"))),
            e.let("hr", _handle_types(e, e.v("name"))),
            e.ret(
                e.eresult_ok(
                    cve_t(e),
                    unwrap_cve_m(
                        e,
                        const_eval_in(
                            e,
                            xx(e),
                            loc(e),
                            e.stage(
                                e.rec(
                                    p("raw", e.lower(e.v("raw"))),
                                    p("type", e.lower(e.fld(e.v("hr"), "type"))),
                                    p("own", e.lower(e.fld(e.v("hr"), "own"))),
                                )
                            ),
                        ),
                    ),
                )
            ),
        ),
        d="d_ops",
    )


def _raw_type(e, x):
    """`wi_raw`: a handle of an interface as a plain value: an i32 by representation (`under`) that converts to i32
    and to the raw handle of any ancestor interface (the spec's `parent` chain; "" is above all), and is made from
    an i32 (the explicit adoption of a handle read from a cell, or a downcast). Two are the same type when their
    names are."""
    desc = "webidl handle"
    def_iface(e, x, "wi_raw_m", p("name", str_(e)))
    def_obj(e, x, "wi_raw", desc, e.rec(p("name", str_(e)), p("under", ty(e)), p("ancestors", e.list_type(str_(e)))))
    x.append(e.impl_interface(e.v("wi_raw"), t(e, "wi_raw_m"), p("name", in_(e, "name"))))
    self_type(
        e,
        x,
        "wi_raw",
        e.cat(e.s("webidl handle "), in_(e, "name")),
        e.mb.if_of(
            [
                (e.eq(a(e, "key"), asp_id(e, "bind")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), asp_id(e, "initial_bind")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), lv(e, "wi_raw_m_id")), e.opt_some(e.mb.types_aspect(), outer(e))),
            ],
            type_aspect(e, xx(e), in_(e, "under"), a(e, "key")),
        ),
        # From itself, its under type (i32) and whatever i32 takes (a constant literal: the null handle `0`).
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), a(e, "source_type")),
                    or_b(
                        e,
                        is_equal(e, xx(e), in_(e, "under"), a(e, "source_type")),
                        type_can_cast_from(e, xx(e), loc(e), in_(e, "under"), a(e, "source_type")),
                    ),
                )
            ),
        ),
        # A runtime value retagged (values.atz): a handle is a wasm i32 value (a constant becomes one first).
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), cve_type(e, a(e, "cv"))), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.let("uv", unwrap_cve_m(e, cast_value(e, xx(e), loc(e), in_(e, "under"), a(e, "cv")))),
            e.match_of(
                e.call(
                    e.mb.reinterpret(),
                    e.tup(loc(e), cve_value(e, e.v("uv")), e.lower(e.fld(e.v("values"), "retag"))),
                ),
                "__t",
                None,
                p(
                    "ok",
                    ret_m(
                        e,
                        ok_cve(
                            e,
                            cv_of(
                                e,
                                cve_code(e, e.v("uv")),
                                bim(e, e.lower(e.fld(e.v("values"), "retag")), "retag", e.v("__t"), outer(e)),
                            ),
                        ),
                    ),
                ),
                p("errs", ret_m(e, err_cve(e, loc(e), desc + ": only runtime values can become one"))),
            ),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), in_(e, "under"), a(e, "dest_type")), ret_m(e, e.mb.as_(e.b(True), bool_t(e)))),
            e.if_only(e.not_(has(e, xx(e), a(e, "dest_type"), "wi_raw_m")), ret_m(e, dfalse(e))),
            e.let("of", acc(e, xx(e), a(e, "dest_type"), "wi_raw_m", "name")),
            e.if_only(e.eq(e.v("of"), e.s("")), ret_m(e, e.mb.as_(e.b(True), bool_t(e)))),
            e.foreach(
                in_(e, "ancestors"),
                "an",
                e.if_only(e.eq(e.v("an"), e.v("of")), ret_m(e, e.mb.as_(e.b(True), bool_t(e)))),
            ),
            e.ret(dfalse(e)),
        ),
        body(e, e.ret(ok_cve(e, retag_values(e, a(e, "cv"), a(e, "dest_type"))))),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "wi_raw_m"),
                    e.eq(in_(e, "name"), acc(e, xx(e), a(e, "other"), "wi_raw_m", "name")),
                )
            ),
        ),
    )
    handle_binding(e, x, "wi_raw_b", desc + " binding")
    handle_binds(e, x, "wi_raw", "under", "wi_raw_b", desc)


def module(e):
    x = []
    x.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    x.append(e.let("webidl", e.import_local("webidl", "webidl.atz")))
    x.append(e.let("values", e.import_local("values", values.FILE)))
    bind_types(e, x)
    for t_ in ["i16", "u16"]:
        x.append(e.let("t_" + t_, e.fld(e.v("wasm"), t_)))
    x.append(e.let("t_pv", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_void"))))
    # The release import's type, lifted (an import's type must be a constant), and the import.
    setup0 = []
    setup0.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    bind_types(e, setup0)
    setup0.append(
        e.let(
            "release_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(p("params", e.list_new(e.mb.eval_type(), e.v("t_i32"))), p("ret", e.v("t_void"))),
            ),
        )
    )
    setup0.append(e.ret(e.rec(p("release_t", e.v("release_t")))))
    x.append(e.let("k0", e.lower(e.mb.seq(setup0))))
    x.append(e.let("release_t", e.fld(e.v("k0"), "release_t")))
    x.append(
        e.let(
            "release",
            e.call(
                e.fld(e.v("wasm"), "import_fn"),
                e.rec(p("module", e.s(MODULE)), p("name", e.s("release")), p("ty", e.v("release_t"))),
            ),
        )
    )
    # The release as a dependency (a callable type, so owned handle types are made as plain types).
    x.append(
        e.let(
            "release_dep",
            e.call(
                e.fld(e.v("wasm"), "func_dep"),
                e.rec(
                    p("name", e.s("webidl_release")),
                    p("params", e.list_new(e.mb.types_string(), e.s("h"))),
                    p("ty", e.v("release_t")),
                    p("body", e.stage(e.call(e.lower(e.v("release")), e.v("h")))),
                ),
            ),
        )
    )
    x.append(e.let("d", e.define()))
    # The definitions that read the spec table (the hook kinds, `webidl.handle`) are a set of their own: the hooks
    # and handle types a module makes and exports reach only `d`, so an importer never loads the table.
    x.append(e.let("d_ops", e.define()))
    x.append(e.option_type_let())
    def_iface(e, x, "wop_m", p("kind", int_t(e)), d="d_ops")
    def_obj(e, x, "wop_t", "webidl binding hook", e.rec(p("kind", int_t(e))), d="d_ops")
    # A hook returning a handle: calls the import (rebuilt from its type and name), then wraps the i32 as an owned
    # handle of the returned interface (`webidl.handle`).
    def_iface(e, x, "wret_m")
    def_obj(e, x, "wret", "webidl owning hook", e.rec(p("ity", ty(e)), p("name", str_(e)), p("wrap", ty(e))))
    _raw_type(e, x)
    x.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
    x.append(e.let("option", e.import_local("option", "option-wasm.atz")))
    _handle_fn(e, x)
    self_type(
        e,
        x,
        "wret",
        e.cat(e.s("webidl owning hook "), in_(e, "name")),
        rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(asp_id(e, "function"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "wret_m"))),
    )
    rt_lift_impl(e, x, "wret")
    rt_bind_impl(e, x, "wret", e.mb.types_string())
    rt_use_impl(e, x, "wret")
    x.append(e.impl_interface(e.v("wret"), t(e, "wret_m")))
    x.append(
        e.impl_interface(
            e.v("wret"),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    # The caller's context may be a target function body (no builtins), so the string is made here.
                    e.let("ref", e.cat(e.s("$"), in_(e, "name"))),
                    e.let("refcv", unwrap_cve_m(e, const_eval_in(e, xx(e), loc(e), e.stage(e.lower(e.v("ref")))))),
                    e.let("fnv", unwrap_cve_m(e, tag_value(e, e.v("refcv"), in_(e, "ity")))),
                    *call_result(
                        e,
                        unwrap_cve_m(
                            e,
                            const_eval_in(
                                e,
                                xx(e),
                                loc(e),
                                e.stage(
                                    e.mb.as_(
                                        e.call(graft(e, e.v("fnv")), graft(e, a(e, "argument"))),
                                        e.lower(in_(e, "wrap")),
                                    )
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )
    # A hook with a nullable result: calls the import (yielding the option's pair), adopts the payload (an owned
    # handle, or the scalar as itself) and makes the option through its `of` constructor.
    def_iface(e, x, "wopt_m")
    def_obj(
        e,
        x,
        "wopt",
        "webidl optional hook",
        e.rec(p("ity", ty(e)), p("name", str_(e)), p("oft", ty(e)), p("pown", ty(e))),
    )
    self_type(
        e,
        x,
        "wopt",
        e.cat(e.s("webidl optional hook "), in_(e, "name")),
        rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(asp_id(e, "function"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "wopt_m"))),
    )
    rt_lift_impl(e, x, "wopt")
    rt_bind_impl(e, x, "wopt", e.mb.types_string())
    rt_use_impl(e, x, "wopt")
    x.append(e.impl_interface(e.v("wopt"), t(e, "wopt_m")))
    x.append(
        e.impl_interface(
            e.v("wopt"),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    e.let("ref", e.cat(e.s("$"), in_(e, "name"))),
                    e.let("refcv", unwrap_cve_m(e, const_eval_in(e, xx(e), loc(e), e.stage(e.lower(e.v("ref")))))),
                    e.let("fnv", unwrap_cve_m(e, tag_value(e, e.v("refcv"), in_(e, "ity")))),
                    *call_result(
                        e,
                        unwrap_cve_m(
                            e,
                            const_eval_in(
                                e,
                                xx(e),
                                loc(e),
                                e.stage(
                                    e.mb.labeled(
                                        "c",
                                        e.seq(
                                            e.let("__r", e.call(graft(e, e.v("fnv")), graft(e, a(e, "argument")))),
                                            e.mb.return_to(
                                                "c",
                                                e.call(
                                                    fn_of(e, e.lower(in_(e, "oft"))),
                                                    e.tup(
                                                        e.mb.field(e.v("__r"), e.n(0)),
                                                        e.mb.as_(
                                                            e.mb.field(e.v("__r"), e.n(1)), e.lower(in_(e, "pown"))
                                                        ),
                                                    ),
                                                ),
                                            ),
                                        ),
                                    )
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )
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
            e.let("c", unwrap_cve_t(e, const_eval_in(e, xx(e), loc(e), e.stage(graft(e, a(e, "cv")))))),
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
                        e.not_(or_b(e, _kind_is(e, "ctor"), _kind_is(e, "callback"))),
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
                                        e,
                                        const_eval_in(
                                            e, xx(e), loc(e), e.stage(e.lower(e.mb.as_(e.v("value"), int_t(e))))
                                        ),
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
                    e.let("wkinds", wkinds),
                    e.let("wrets", wrets),
                    # The parameter types: handles as the raw handle type of their interface, the rest by kind.
                    e.let("params", e.list_new(ty(e))),
                    e.if_only(
                        e.call_m(e.v("sig"), "self", e.tup()),
                        push(e, e.v("params"), _raw_of(e, e.call_m(e.v("sig"), "iface", e.tup()))),
                    ),
                    # A callback hook's one parameter: the callable's `(call, object)` pair (closure.callback_of),
                    # the call's function type derived from the callback's signature: the object pointer, then its
                    # arguments (a handle or a string as a new owned handle of its interface, an optional or nullable
                    # one as a presence flag then the value) as one parameter (a tuple of them when several), and its
                    # scalar result.
                    e.if_only(
                        _kind_is(e, "callback"),
                        e.seq(
                            e.let("cparams", e.list_new(ty(e))),
                            e.foreach(
                                e.call_m(e.v("sig"), "cb_args", e.tup()),
                                "cp",
                                e.seq(
                                    e.if_only(
                                        e.call_m(e.v("cp"), "optional", e.tup()),
                                        push(e, e.v("cparams"), e.call_m(e.v("wkinds"), "get", e.s("flag"))),
                                    ),
                                    e.if_only(
                                        e.call_m(e.v("cp"), "nullable", e.tup()),
                                        push(e, e.v("cparams"), e.call_m(e.v("wkinds"), "get", e.s("flag"))),
                                    ),
                                    e.if_only(
                                        e.eq(e.call_m(e.v("cp"), "kind", e.tup()), e.s("buf")),
                                        ret_m(
                                            e,
                                            err_cve(
                                                e,
                                                loc(e),
                                                e.cat(
                                                    e.s("webidl: buffer callback arguments are not supported: "),
                                                    e.v("iface"),
                                                ),
                                            ),
                                        ),
                                    ),
                                    e.if_else(
                                        or_b(
                                            e,
                                            e.eq(e.call_m(e.v("cp"), "kind", e.tup()), e.s("handle")),
                                            e.eq(e.call_m(e.v("cp"), "kind", e.tup()), e.s("str")),
                                        ),
                                        push(
                                            e,
                                            e.v("cparams"),
                                            e.fld(_handle_types(e, e.call_m(e.v("cp"), "iface", e.tup())), "type"),
                                        ),
                                        push(
                                            e,
                                            e.v("cparams"),
                                            e.call_m(e.v("wkinds"), "get", e.call_m(e.v("cp"), "kind", e.tup())),
                                        ),
                                    ),
                                ),
                            ),
                            e.let("crk", e.call_m(e.v("sig"), "cb_ret", e.tup())),
                            e.if_only(
                                or_b(
                                    e,
                                    e.eq(e.v("crk"), e.s("handle")),
                                    or_b(e, e.eq(e.v("crk"), e.s("str")), e.eq(e.v("crk"), e.s("buf"))),
                                ),
                                ret_m(
                                    e,
                                    err_cve(
                                        e,
                                        loc(e),
                                        e.cat(
                                            e.s("webidl: callback result of kind "),
                                            e.v("crk"),
                                            e.s(" is not supported: "),
                                            e.v("iface"),
                                        ),
                                    ),
                                ),
                            ),
                            e.let("cret", e.call_m(e.v("wrets"), "get", e.v("crk"))),
                            count_let(e, "ncp"),
                            count_loop(e, "ncp", e.v("cparams")),
                            e.let("fparams", e.list_new(ty(e), e.lower_v("t_pv"))),
                            e.if_only(
                                e.eq(e.fld(e.v("ncp"), "v"), e.int_of(1)),
                                push(e, e.v("fparams"), e.call_m(e.v("cparams"), "get", e.int_of(0))),
                            ),
                            e.if_only(
                                e.mb.operator_gt(e.fld(e.v("ncp"), "v"), e.int_of(1)),
                                push(e, e.v("fparams"), e.call(e.lower(e.fld(e.v("wasm"), "tuple")), e.v("cparams"))),
                            ),
                            e.let(
                                "callt",
                                e.call(
                                    e.lower(e.fld(e.v("wasm"), "fn")),
                                    e.rec(p("params", e.v("fparams")), p("ret", e.v("cret"))),
                                ),
                            ),
                            push(
                                e,
                                e.v("params"),
                                e.call(
                                    e.lower(e.fld(e.v("wasm"), "tuple")),
                                    e.list_new(
                                        ty(e),
                                        e.call(e.lower(e.fld(e.v("wasm"), "fnref")), e.v("callt")),
                                        e.lower_v("t_pv"),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.if_only(
                        e.not_(_kind_is(e, "callback")),
                        e.foreach(
                            e.call_m(e.v("sig"), "args", e.tup()),
                            "ap",
                            e.seq(
                                e.if_only(
                                    e.call_m(e.v("ap"), "optional", e.tup()),
                                    push(e, e.v("params"), e.call_m(e.v("wkinds"), "get", e.s("flag"))),
                                ),
                                e.if_only(
                                    e.call_m(e.v("ap"), "nullable", e.tup()),
                                    push(e, e.v("params"), e.call_m(e.v("wkinds"), "get", e.s("flag"))),
                                ),
                                e.if_else(
                                    or_b(
                                        e,
                                        e.eq(e.call_m(e.v("ap"), "kind", e.tup()), e.s("str")),
                                        e.eq(e.call_m(e.v("ap"), "kind", e.tup()), e.s("buf")),
                                    ),
                                    e.seq(
                                        push(e, e.v("params"), e.call_m(e.v("wkinds"), "get", e.s("ptr"))),
                                        push(e, e.v("params"), e.call_m(e.v("wkinds"), "get", e.s("len"))),
                                    ),
                                    e.if_else(
                                        e.eq(e.call_m(e.v("ap"), "kind", e.tup()), e.s("handle")),
                                        push(e, e.v("params"), _raw_of(e, e.call_m(e.v("ap"), "iface", e.tup()))),
                                        push(
                                            e,
                                            e.v("params"),
                                            e.call_m(e.v("wkinds"), "get", e.call_m(e.v("ap"), "kind", e.tup())),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.let("ret_out", e.call_m(e.v("sig"), "ret_out", e.tup())),
                    e.let("rkind", e.call_m(e.v("sig"), "ret_kind", e.tup())),
                    e.let("rhandle", or_b(e, e.eq(e.v("rkind"), e.s("handle")), e.eq(e.v("rkind"), e.s("str")))),
                    e.let(
                        "rty",
                        e.if_else(
                            e.v("ret_out"),
                            e.call(
                                e.lower(e.fld(e.v("wasm"), "tuple")),
                                e.list_new(
                                    ty(e),
                                    e.call_m(e.v("wrets"), "get", e.s("i32")),
                                    e.call_m(e.v("wrets"), "get", e.v("rkind")),
                                ),
                            ),
                            e.call_m(e.v("wrets"), "get", e.v("rkind")),
                        ),
                    ),
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
                        unwrap_cve_m(
                            e, const_eval_in(e, xx(e), loc(e), e.stage(e.cat(e.s("$"), e.lower(e.v("name")))))
                        ),
                    ),
                    e.if_only(
                        e.v("ret_out"),
                        e.seq(
                            e.let(
                                "rhts",
                                e.if_else(
                                    e.v("rhandle"),
                                    _handle_types(e, e.call_m(e.v("sig"), "ret_iface", e.tup())),
                                    e.rec(
                                        p("type", e.call_m(e.v("wrets"), "get", e.v("rkind"))),
                                        p("own", e.call_m(e.v("wrets"), "get", e.v("rkind"))),
                                    ),
                                ),
                            ),
                            e.let(
                                "optr",
                                unwrap_m(
                                    e,
                                    try_er(
                                        e,
                                        e.call(
                                            e.lower(e.fld(e.v("option"), "types")),
                                            e.rec(
                                                p("xx", xx(e)), p("loc", loc(e)), p("elem", e.fld(e.v("rhts"), "type"))
                                            ),
                                        ),
                                        e.lower(e.fld(e.v("option"), "types_t")),
                                    ),
                                    cve_t(e),
                                ),
                            ),
                            ret_m(
                                e,
                                ok_cve(
                                    e,
                                    cv_of(
                                        e,
                                        code_none(e, loc(e)),
                                        e.call(
                                            e.eval_builtin("value_object_const"),
                                            e.rec(
                                                p(
                                                    "type",
                                                    mk(
                                                        e,
                                                        "wopt",
                                                        p("ity", e.v("ity")),
                                                        p("name", e.v("name")),
                                                        p("oft", e.fld(e.v("optr"), "of_t")),
                                                        p("pown", e.fld(e.v("rhts"), "own")),
                                                    ),
                                                ),
                                                p("data", as_object(e, e.v("name"))),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.if_only(
                        e.v("rhandle"),
                        ret_m(
                            e,
                            ok_cve(
                                e,
                                cv_of(
                                    e,
                                    code_none(e, loc(e)),
                                    e.call(
                                        e.eval_builtin("value_object_const"),
                                        e.rec(
                                            p(
                                                "type",
                                                mk(
                                                    e,
                                                    "wret",
                                                    p("ity", e.v("ity")),
                                                    p("name", e.v("name")),
                                                    p(
                                                        "wrap",
                                                        e.fld(
                                                            _handle_types(
                                                                e, e.call_m(e.v("sig"), "ret_iface", e.tup())
                                                            ),
                                                            "own",
                                                        ),
                                                    ),
                                                ),
                                            ),
                                            # The import's name: the data a lifted hook exports (as a string).
                                            p("data", as_object(e, e.v("name"))),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.ret(tag_value(e, e.v("refcv"), e.v("ity"))),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )
    x.append(e.finish(e.v("d")))
    x.append(e.finish(e.v("d_ops")))
    defs = []
    defs.append(p("wop_t_new", e.fld(e.v("wop_t"), "new")))
    defs.append(p("wret_new", e.fld(e.v("wret"), "new")))
    defs.append(p("handle", e.fld(e.v("handle_b"), "func")))
    defs.append(p("t_i32", e.v("t_i32")))
    defs.append(p("release_t", e.v("release_t")))
    defs.append(
        p(
            "global_t",
            e.call(e.fld(e.v("wasm"), "fn"), e.rec(p("params", e.list_new(e.mb.eval_type())), p("ret", e.v("t_i32")))),
        )
    )
    x.append(e.ret(e.rec(*defs)))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    exports = []
    exports.append(p("module", e.s(MODULE)))
    top.append(e.let("gfn_d", e.define()))
    # The hook kinds as const functions: each calls its kind object's function aspect with the caller's argument.
    for kind in KINDS:
        top.append(
            e.let(
                kind + "_o",
                e.call(
                    e.fld(e.v("k"), "wop_t_new"),
                    e.rec(p("kind", e.int_of(_kind_of(kind)))),
                ),
            )
        )
        const_fn(
            e,
            top,
            kind + "_b",
            "webidl." + kind,
            bim(
                e,
                asp_iface(e, "function"),
                "call",
                e.lower(e.v(kind + "_o")),
                e.rec(
                    p("xx", xx(e)),
                    p("loc", loc(e)),
                    p(
                        "function",
                        cv_of(
                            e, code_none(e, loc(e)), e.call(e.eval_builtin("value_empty"), e.lower(e.v(kind + "_o")))
                        ),
                    ),
                    p("argument", a(e, "argument")),
                ),
            ),
            d="gfn_d",
        )
        exports.append(p(kind, e.fld(e.v(kind + "_b"), "func")))
    exports.append(p("handle", e.fld(e.v("k"), "handle")))
    # `global` is a set of its own: code that calls it (in a function body) reaches only it, not the hook kinds
    # (whose definitions reach the spec table).
    top.append(e.let("gfn_global", e.define()))
    for special in ["global"]:
        ity = e.call(
            e.fld(e.v("wasm"), "import_t"),
            e.rec(p("module", e.s(MODULE)), p("name", e.s(special)), p("ty", e.fld(e.v("k"), special + "_t"))),
        )
        top.append(
            e.let(
                special + "_o",
                e.call(
                    e.fld(e.v("k"), "wret_new"),
                    e.rec(
                        p("ity", ity),
                        p("name", e.s(special)),
                        p(
                            "wrap",
                            e.fld(
                                e.call(e.fld(e.v("k"), "handle"), e.s("Window" if special == "global" else "")), "own"
                            ),
                        ),
                    ),
                ),
            )
        )
        const_fn(
            e,
            top,
            special + "_b",
            "webidl." + special,
            bim(
                e,
                asp_iface(e, "function"),
                "call",
                e.lower(e.v(special + "_o")),
                e.rec(
                    p("xx", xx(e)),
                    p("loc", loc(e)),
                    p(
                        "function",
                        cv_of(
                            e, code_none(e, loc(e)), e.call(e.eval_builtin("value_empty"), e.lower(e.v(special + "_o")))
                        ),
                    ),
                    p("argument", a(e, "argument")),
                ),
            ),
            d="gfn_global",
        )
        exports.append(p(special, e.fld(e.v(special + "_b"), "func")))
    top.append(e.finish(e.v("gfn_d")))
    top.append(e.finish(e.v("gfn_global")))
    top.append(e.ret(e.rec(*exports)))
    return top
