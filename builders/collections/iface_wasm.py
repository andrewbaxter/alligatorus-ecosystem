"""iface-wasm.atz: interface values on the wasm target: a value whose concrete type is unknown where it is used,
dispatching its methods at runtime (docs/wat-closures.md §2).

`iface.declare({methods: {name: {arg, ret}, ...}})` yields `{type, own, raw}`: `raw` the interface value type, `type`
its owned form (destructor.atz) and `own` the adopting type. An interface value is the pair `(object: ptr(void),
vtable: ptr(i32))` (a wasm tuple): the vtable holds the table index (wat-2.0's `fnref`) of each method's function in
declaration order, then of the implementation's destroy. `v.name(arg)` calls through the vtable with the object
pointer first; dropping an owned interface value destroys the object through the vtable's last entry. A method's
`arg` is one wasm type (`void` for none) and `ret` one wasm type (`void` for none).

`iface.impl({iface, self, methods: {name: fn, ...}})` for the owned handle type `self` (destructor.atz: its
`owned_m` gives the under type and the destroy function) and one function per declared method (a function
dependency, given as its type, or any function value the table takes) of type `fn([under, arg], ret)`
(`fn([under], ret)` for a `void` arg)
yields `{upcast}`: `upcast(u)` (a function dependency) is the interface value over the under value `u`; `upcast(v
.forget()) as own` makes an owned interface value out of an owned `v`, which now belongs to it. The vtable is one data
segment per implementation and module (`fnref_dep`).

Method arguments and results are scalars (an i32 handle, a pointer, a number); tuples are not taken.

`it_m` is the interface value types' interface (fields `id`, `methods`, `pt`, `pv`, `pi32`, `i32`), for libraries
building on interface values (closure-wasm.atz).
"""

from ..eco_mb import p
from ..core import values
from ..memory import destructor
from ..target_mb import (
    fn_type_of,
    up,
    a,
    acc,
    accessor,
    as_object,
    asp_iface,
    bim,
    bim0,
    body,
    call_result,
    code_none,
    const_eval_in,
    const_fn,
    const_type_arg,
    conv,
    cv_of,
    cve_code,
    cve_type,
    cve_value,
    def_obj,
    err_cve,
    fn_of,
    fresh_unique,
    graft,
    handle_type,
    has,
    has_b,
    in_,
    is_equal,
    key_str,
    loc,
    lookup,
    lookup_v,
    lt,
    mk,
    ok_cve,
    outer,
    recv_of,
    ret_m,
    staged_in,
    t,
    try_er,
    ty,
    ty_desc,
    unique_t,
    unwrap_cve_m,
    xx,
)
from .record_wasm import argument, field, record_fields

FILE = "iface-wasm.atz"

# Stage depths (as vec.py): a dependency body made in a const function's host body is two stages below the module
# and one below the host locals.
BODY_MOD = 2
BODY_HOST = 1


def _it(e, x):
    """The interface value type `it`: a handle over the pair tuple, whose fields are the declared methods."""
    fields = [
        p("id", unique_t(e)),
        p("methods", e.list_type(t(e, "imeth"))),
        p("pt", ty(e)),
        p("pv", ty(e)),
        p("pi32", ty(e)),
        p("i32", ty(e)),
    ]

    def method_value():
        return cv_of(
            e,
            cve_code(e, a(e, "value")),
            e.call(
                e.eval_builtin("value_object_const"),
                e.rec(
                    p("type", mk(e, "it_meth", p("kind", e.v("key")), p("ht", outer(e)))),
                    p("data", as_object(e, cv_of(e, code_none(e, loc(e)), cve_value(e, a(e, "value"))))),
                ),
            ),
        )

    field_body = body(
        e,
        e.if_only(
            e.not_(has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
            ret_m(e, err_cve(e, loc(e), "interface: field must be a constant string")),
        ),
        e.let(
            "key",
            bim(
                e,
                e.mb.eval_aspect_string_const(),
                "get",
                lookup_v(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const()),
                cve_value(e, a(e, "key")),
            ),
        ),
        e.foreach(
            in_(e, "methods"),
            "m0",
            e.if_only(e.eq(e.call_m(e.v("m0"), "name", e.tup()), e.v("key")), ret_m(e, ok_cve(e, method_value()))),
        ),
        e.ret(err_cve(e, loc(e), e.cat(e.s("interface has no method "), e.v("key")))),
    )
    keys = e.seq(
        e.let("ks", e.list_new(e.mb.types_constkey())),
        e.foreach(
            in_(e, "methods"),
            "m0",
            e.push(e.v("ks"), e.mb.as_(e.call_m(e.v("m0"), "name", e.tup()), e.mb.types_constkey())),
        ),
        e.ret(e.v("ks")),
    )
    handle_type(
        e,
        x,
        "it",
        "it_m",
        "interface",
        fields,
        {},
        [],
        under="pt",
        from_under=True,
        desc_expr=e.s("interface"),
        identity="id",
        identity_eq=lambda e_, xx_, mine, theirs: e_.eq(mine, theirs),
        field=(field_body, keys),
        extra_dispatch=[(e.lower(e.v("size_id")), outer(e)), (e.lower(e.v("align_id")), outer(e))],
    )
    # An interface value's size (values.atz): the pair's two i32s, so records and vecs can hold one.
    x.append(e.impl_interface(e.v("it"), e.fld(e.v("values"), "size_i"), p("size", e.int_of(8))))
    x.append(e.impl_interface(e.v("it"), e.fld(e.v("values"), "align_i"), p("align", e.int_of(4))))
    # The bound method's call: the method's index in the interface, its function type over the object pointer, and
    # the staged call through the vtable (in the caller's code).
    x.append(
        e.impl_interface(
            e.v("it_meth"),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    e.let("recv", recv_of(e)),
                    e.let("ht", in_(e, "ht")),
                    e.let("found", e.rec(p("v", e.opt_none(lt(e, "imeth"))))),
                    e.let("k", e.rec(p("v", e.int_of(0)))),
                    e.let("i", e.rec(p("v", e.int_of(0)))),
                    e.foreach(
                        acc(e, xx(e), e.v("ht"), "it_m", "methods"),
                        "m0",
                        e.seq(
                            e.if_only(
                                e.eq(e.call_m(e.v("m0"), "name", e.tup()), in_(e, "kind")),
                                e.seq(
                                    e.mb.set(e.fld(e.v("found"), "v"), e.opt_some(lt(e, "imeth"), e.v("m0"))),
                                    e.mb.set(e.fld(e.v("k"), "v"), e.fld(e.v("i"), "v")),
                                ),
                            ),
                            e.incr(e.fld(e.v("i"), "v")),
                        ),
                    ),
                    e.if_only(
                        e.not_(e.fld(e.fld(e.v("found"), "v"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), e.cat(e.s("interface has no method "), in_(e, "kind")))),
                    ),
                    e.let("m", e.fld(e.fld(e.v("found"), "v"), "value")),
                    e.let("marg", e.call_m(e.v("m"), "arg", e.tup())),
                    e.let("mret", e.call_m(e.v("m"), "ret", e.tup())),
                    e.let("pv", acc(e, xx(e), e.v("ht"), "it_m", "pv")),
                    e.let("pt", acc(e, xx(e), e.v("ht"), "it_m", "pt")),
                    e.let("noarg", is_equal(e, xx(e), e.v("marg"), e.lower(e.v("void")))),
                    e.let(
                        "fnt",
                        e.if_else(
                            e.v("noarg"),
                            fn_type_of(e, e.lower(e.v("lib")), [e.v("pv")], e.v("mret")),
                            fn_type_of(e, e.lower(e.v("lib")), [e.v("pv"), e.v("marg")], e.v("mret")),
                        ),
                    ),
                    e.let("frt", e.call(e.lower(e.fld(e.v("lib"), "fnref")), e.v("fnt"))),
                    e.let("kidx", e.fld(e.v("k"), "v")),
                    *call_result(
                        e,
                        staged_in(
                            e,
                            e.mb.labeled(
                                "c",
                                e.seq(
                                    e.let("__s", e.mb.as_(graft(e, e.v("recv")), e.lower(e.v("pt")))),
                                    e.let("__o", e.mb.field(e.v("__s"), e.n(0))),
                                    e.let("__v", e.mb.field(e.v("__s"), e.n(1))),
                                    e.let(
                                        "__f",
                                        conv(
                                            e,
                                            up(e, e.fld(e.v("lib"), "int_to_fnref"), BODY_MOD),
                                            e.mb.field(e.v("__v"), e.lower(e.v("kidx"))),
                                            e.lower(e.v("frt")),
                                        ),
                                    ),
                                    e.mb.return_to(
                                        "c",
                                        e.if_else(
                                            e.lower(e.v("noarg")),
                                            e.call(e.v("__f"), e.v("__o")),
                                            e.call(e.v("__f"), e.tup(e.v("__o"), graft(e, a(e, "argument")))),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )


def _declare(e, x):
    """`iface.declare`: the method list from the record, the pair type, the destroy dependency, the owned type."""
    parts = []
    parts += argument(e, "iface.declare", "fields")
    parts.append(e.let("mcv", field(e, e.v("fields"), "methods")))
    parts += record_fields(e, "iface.declare", e.v("mcv"), "mfields")
    parts.append(e.let("methods", e.list_new(lt(e, "imeth"))))
    parts.append(
        e.foreach(
            e.v("mfields"),
            "ment",
            e.seq(
                e.let("mname", key_str(e, e.fld(e.v("ment"), "key"))),
                e.let("sigcv", unwrap_cve_m(e, e.fld(e.v("ment"), "value"))),
                *record_fields(e, "iface.declare", e.v("sigcv"), "sig"),
                *const_type_arg(e, "iface.declare", field(e, e.v("sig"), "arg"), "margt"),
                *const_type_arg(e, "iface.declare", field(e, e.v("sig"), "ret"), "mrett"),
                e.push(
                    e.v("methods"),
                    mk(e, "imeth", p("name", e.v("mname")), p("arg", e.v("margt")), p("ret", e.v("mrett"))),
                ),
            ),
        )
    )
    parts.append(e.let("n", e.rec(p("v", e.int_of(0)))))
    parts.append(e.foreach(e.v("methods"), "_", e.incr(e.fld(e.v("n"), "v"))))
    parts.append(e.let("pv", e.lower(e.v("pv"))))
    parts.append(e.let("pi32", e.lower(e.v("pi32"))))
    parts.append(e.let("i32", e.lower(e.v("i32"))))
    parts.append(e.let("pt", e.lower(e.v("pt"))))
    parts.append(e.let("destroy_t", fn_type_of(e, e.lower(e.v("lib")), [e.v("pt")], e.lower(e.v("void")))))
    parts.append(
        e.let(
            "dref_t",
            e.call(
                e.lower(e.fld(e.v("lib"), "fnref")),
                fn_type_of(e, e.lower(e.v("lib")), [e.v("pv")], e.lower(e.v("void"))),
            ),
        )
    )
    parts.append(e.let("nidx", e.fld(e.v("n"), "v")))
    # destroy(v): the vtable's entry after the methods, called with the object pointer
    parts.append(
        e.let(
            "destroy",
            e.call(
                e.lower(e.fld(e.v("lib"), "func_dep")),
                e.rec(
                    p("name", e.s("iface_destroy")),
                    p("params", e.list_new(e.mb.types_string(), e.s("v"))),
                    p("ty", e.v("destroy_t")),
                    p(
                        "body",
                        e.stage(
                            e.seq(
                                e.let("__v", e.mb.field(e.v("v"), e.n(1))),
                                e.let(
                                    "__f",
                                    conv(
                                        e,
                                        up(e, e.fld(e.v("lib"), "int_to_fnref"), BODY_MOD),
                                        e.mb.field(e.v("__v"), up(e, e.v("nidx"), BODY_HOST)),
                                        up(e, e.v("dref_t"), BODY_HOST),
                                    ),
                                ),
                                e.call(e.v("__f"), e.mb.field(e.v("v"), e.n(0))),
                            )
                        ),
                    ),
                ),
            ),
        )
    )
    parts.append(
        e.ret(
            const_eval_in(
                e,
                xx(e),
                loc(e),
                e.stage(
                    e.mb.labeled(
                        "__r",
                        e.seq(
                            e.let(
                                "__raw",
                                e.mb.as_(
                                    e.call(
                                        up(e, e.fld(e.v("it"), "new"), BODY_MOD),
                                        e.rec(
                                            p("id", fresh_unique(e)),
                                            p("methods", e.lower(e.v("methods"))),
                                            p("pt", e.lower(e.v("pt"))),
                                            p("pv", e.lower(e.v("pv"))),
                                            p("pi32", e.lower(e.v("pi32"))),
                                            p("i32", e.lower(e.v("i32"))),
                                        ),
                                    ),
                                    e.mb.eval_type(),
                                ),
                            ),
                            e.let(
                                "__owned",
                                e.call(
                                    e.fld(up(e, e.v("destructor"), BODY_MOD), "type"),
                                    e.rec(p("under", e.v("__raw")), p("destroy", fn_of(e, e.lower(e.v("destroy"))))),
                                ),
                            ),
                            e.mb.return_to(
                                "__r",
                                e.rec(
                                    p("type", e.fld(e.v("__owned"), "type")),
                                    p("own", e.fld(e.v("__owned"), "own")),
                                    p("raw", e.v("__raw")),
                                ),
                            ),
                        ),
                    )
                ),
            )
        )
    )
    const_fn(e, x, "declare_b", "iface.declare", body(e, *parts))


def _impl(e, x):
    """`iface.impl`: checks the implementation's functions against the declaration, makes the vtable segment and
    the upcast dependency."""
    parts = []
    parts += argument(e, "iface.impl", "fields")
    parts += const_type_arg(e, "iface.impl", field(e, e.v("fields"), "iface"), "ifacet")
    parts += const_type_arg(e, "iface.impl", field(e, e.v("fields"), "self"), "selft")
    parts.append(e.let("owned_m", e.lower(e.fld(e.v("destructor"), "owned_m"))))
    # the raw interface type (the owned one's under)
    parts.append(
        e.let(
            "raw",
            e.if_else(
                has_b(e, xx(e), e.v("ifacet"), e.v("owned_m")),
                bim0(e, e.v("owned_m"), "under", e.fld(lookup(e, xx(e), e.v("ifacet"), e.v("owned_m")), "value")),
                e.v("ifacet"),
            ),
        )
    )
    parts.append(
        e.if_only(
            e.not_(has(e, xx(e), e.v("raw"), "it_m")),
            ret_m(e, err_cve(e, loc(e), e.cat(e.s("iface.impl: iface is not an interface: "), ty_desc(e, e.v("raw"))))),
        )
    )
    parts.append(
        e.if_only(
            e.not_(has_b(e, xx(e), e.v("selft"), e.v("owned_m"))),
            ret_m(
                e, err_cve(e, loc(e), e.cat(e.s("iface.impl: self is not an owned type: "), ty_desc(e, e.v("selft"))))
            ),
        )
    )
    parts.append(e.let("sk", e.fld(lookup(e, xx(e), e.v("selft"), e.v("owned_m")), "value")))
    parts.append(e.let("under", bim0(e, e.v("owned_m"), "under", e.v("sk"))))
    parts.append(e.let("dv", e.mb.as_(bim0(e, e.v("owned_m"), "destroy", e.v("sk")), e.mb.eval_value())))
    parts.append(e.let("mcv", field(e, e.v("fields"), "methods")))
    parts += record_fields(e, "iface.impl", e.v("mcv"), "mfields")
    parts.append(e.let("keys", e.list_new(e.lower(e.fld(e.v("lib"), "fnkey_t")))))
    parts.append(e.let("pv", acc(e, xx(e), e.v("raw"), "it_m", "pv")))
    parts.append(e.let("pt", acc(e, xx(e), e.v("raw"), "it_m", "pt")))

    def fn_key(cv):
        return unwrap_cve_m(
            e,
            try_er(
                e,
                e.call(e.lower(e.fld(e.v("lib"), "fn_key")), e.rec(p("xx", xx(e)), p("loc", loc(e)), p("cv", cv))),
                e.lower(e.fld(e.v("lib"), "fnkey_t")),
            ),
        )

    def check_fn(key, expected, what):
        return e.if_only(
            e.not_(is_equal(e, xx(e), e.call_m(key, "fn", e.tup()), expected)),
            ret_m(
                e,
                err_cve(
                    e,
                    loc(e),
                    e.cat(
                        e.s("iface.impl: "),
                        what,
                        e.s(" has type "),
                        ty_desc(e, e.call_m(key, "fn", e.tup())),
                        e.s(", not "),
                        ty_desc(e, expected),
                    ),
                ),
            ),
        )

    parts.append(
        e.foreach(
            acc(e, xx(e), e.v("raw"), "it_m", "methods"),
            "m0",
            e.seq(
                e.let("mname", e.call_m(e.v("m0"), "name", e.tup())),
                e.let("margt", e.call_m(e.v("m0"), "arg", e.tup())),
                e.let(
                    "expected",
                    e.if_else(
                        is_equal(e, xx(e), e.v("margt"), e.lower(e.v("void"))),
                        fn_type_of(e, e.lower(e.v("lib")), [e.v("under")], e.call_m(e.v("m0"), "ret", e.tup())),
                        fn_type_of(
                            e, e.lower(e.v("lib")), [e.v("under"), e.v("margt")], e.call_m(e.v("m0"), "ret", e.tup())
                        ),
                    ),
                ),
                e.let("fcv", field(e, e.v("mfields"), e.v("mname"))),
                e.let("key", fn_key(e.v("fcv"))),
                check_fn(e.v("key"), e.v("expected"), e.cat(e.s("method "), e.v("mname"))),
                e.push(e.v("keys"), e.v("key")),
            ),
        )
    )
    parts.append(e.let("dkey", fn_key(cv_of(e, code_none(e, loc(e)), e.v("dv")))))
    parts.append(
        check_fn(
            e.v("dkey"),
            fn_type_of(e, e.lower(e.v("lib")), [e.v("under")], e.lower(e.v("void"))),
            e.s("the destroy function"),
        )
    )
    parts.append(e.push(e.v("keys"), e.v("dkey")))
    parts.append(
        e.let(
            "vt",
            e.call(
                e.lower(e.fld(e.v("lib"), "fnref_dep_keys")), e.rec(p("name", e.s("vtable")), p("keys", e.v("keys")))
            ),
        )
    )
    parts.append(e.let("upcast_t", fn_type_of(e, e.lower(e.v("lib")), [e.v("under")], e.v("raw"))))
    # upcast(u): the pair of the object pointer and the vtable's address, as the interface
    parts.append(
        e.let(
            "upcast",
            e.call(
                e.lower(e.fld(e.v("lib"), "func_dep")),
                e.rec(
                    p("name", e.s("upcast")),
                    p("params", e.list_new(e.mb.types_string(), e.s("u"))),
                    p("ty", e.v("upcast_t")),
                    p(
                        "body",
                        e.stage(
                            e.seq(
                                e.ret(
                                    e.mb.as_(
                                        e.mb.as_(
                                            e.tup(
                                                e.mb.as_(e.v("u"), up(e, e.v("pv"), BODY_HOST)),
                                                e.mb.as_(
                                                    e.call(fn_of(e, up(e, e.v("vt"), BODY_HOST)), e.tup()),
                                                    up(e, e.v("pi32"), BODY_MOD),
                                                ),
                                            ),
                                            up(e, e.v("pt"), BODY_HOST),
                                        ),
                                        up(e, e.v("raw"), BODY_HOST),
                                    )
                                )
                            )
                        ),
                    ),
                ),
            ),
        )
    )
    parts.append(e.ret(const_eval_in(e, xx(e), loc(e), e.stage(e.rec(p("upcast", e.lower(e.v("upcast"))))))))
    const_fn(e, x, "impl_b", "iface.impl", body(e, *parts))


def module(e):
    x = []
    x.append(e.let("lib", e.import_local("wasm", "wat-2.0.atz")))
    x.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("size_id", e.fld(e.v("values"), "size_id")))
    x.append(e.let("align_id", e.fld(e.v("values"), "align_id")))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    x.append(e.let("void", e.fld(e.v("lib"), "void")))
    x.append(e.let("i32", e.fld(e.v("lib"), "i32")))
    x.append(e.let("pv", e.call(e.fld(e.v("lib"), "ptr"), e.v("void"))))
    x.append(e.let("pi32", e.call(e.fld(e.v("lib"), "ptr"), e.v("i32"))))
    x.append(e.let("pt", e.call(e.fld(e.v("lib"), "tuple"), e.list_new(e.mb.eval_type(), e.v("pv"), e.v("pi32")))))
    def_obj(e, x, "imeth", "interface method", e.rec(p("name", e.mb.types_string()), p("arg", ty(e)), p("ret", ty(e))))
    for f, ft in [("name", e.mb.types_string()), ("arg", ty(e)), ("ret", ty(e))]:
        accessor(e, x, "imeth", f, ft)
    _it(e, x)
    _declare(e, x)
    _impl(e, x)
    x.append(e.finish(e.v("d")))
    x.append(
        e.ret(
            e.rec(
                p("declare", e.fld(e.v("declare_b"), "func")),
                p("impl", e.fld(e.v("impl_b"), "func")),
                p("it_m", t(e, "it_m")),
            )
        )
    )

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(*[p(n, e.fld(e.v("k"), n)) for n in ["declare", "impl", "it_m"]])))
    return top
