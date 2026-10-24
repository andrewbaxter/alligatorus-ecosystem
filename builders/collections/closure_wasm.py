"""closure-wasm.atz: closures on the wasm target as sugar over an object and a method (docs/wat-closures.md §3): a
heap record of explicit captures (record-wasm.atz's machinery) behind a one-method interface (iface-wasm.atz).

`closure.callable({arg, ret})` declares the interface of callables taking `arg` and returning `ret` (one method,
`call`): `iface.declare`'s `{type, own, raw}`. A module declares it once per signature, so every closure of that
signature is a value of the same type.

`closure.new({callable, capture: {name: type, ...}, body: stage(...)})` yields `{make}`: `make` is a constant
callable whose call `make({name: value, ...})` allocates the record (wasm-alloc.atz) holding the captures and yields
the owned callable value over it (`callable` is the owned callable type). `body` is the `call` method's body: it sees
`self`, the record as a handle whose fields are the captures (`self.name` reads and assigns the capture's place; a
capture of an owned type (destructor.atz) is stored as its under value, given to `make` as an owned value (a
temporary or `v.move()`), read as a borrow and destroyed with the closure), and `arg` (absent for a `void`
argument). The body cannot see the enclosing
function's locals: a capture is a value copied (or moved) into the record. Dropping the owned callable value runs the
closure's destroy: the owned captures' destroys, then the record's `free`. A closure without captures has no record
(a null object pointer).

`closure.of({callable, fn})` yields `{make}` for a plain function `fn` (a dependency, given as its type) of type
`fn([ptr(void), arg], ret)`
(`fn([ptr(void)], ret)` for a `void` arg): `make(())` is an owned callable value over a null object pointer with a
no-op destroy; its receiver parameter is the null pointer.

`closure.callback_of(c)`, for a callable value `c` (raw or owned), is the wasm tuple `(call, object)` a WebIDL
callback hook takes as its one argument (`h(closure.callback_of(c))`, webidl-wasm.atz): the reference
(`fnref(fn([ptr(void), arg], ret))`, the vtable's first entry) to its `call` function and its object pointer
(`ptr(void)`). The hook checks the reference's function type against the callback's signature.
"""

from ..eco_mb import p
from ..target_mb import (
    up,
    fn_type_of,
    a,
    bim0,
    body,
    call_result,
    const_eval_in,
    const_fn,
    const_type_arg,
    conv,
    cve_type,
    err_cve,
    fn_of,
    fresh_unique,
    graft,
    has_b,
    in_,
    is_equal,
    loc,
    lookup,
    lookup_v,
    lt,
    mk,
    ok_cve,
    retag_values,
    ret_m,
    staged_in,
    ty,
    ty_desc,
    xx,
)
from . import iface_wasm, record_wasm
from .record_wasm import BODY_MOD, CTOR_TYPES, alloc, argument, field

FILE = "closure-wasm.atz"

# A const function's staged result is one stage below its host body and two below the module.
OUT_MOD = 2


def _cctor(e, x):
    """The callable constructor type `cctor`: `make` (the record, then the pair of its pointer and the vtable's
    address, as the callable type `raw`) and `of` (the pair over a null pointer)."""

    def pair():
        return e.mb.as_(
            e.mb.as_(
                e.tup(
                    e.mb.as_(e.v("__p"), e.lower(in_(e, "pv"))),
                    e.mb.as_(e.call(fn_of(e, e.lower(in_(e, "vt"))), e.tup()), e.lower(in_(e, "pi32"))),
                ),
                e.lower(in_(e, "pt")),
            ),
            e.lower(in_(e, "raw")),
        )

    make = [
        e.let(
            "store",
            e.mb.as_(mk(e, "rctor", p("kind", e.s("store")), *[p(f, in_(e, f)) for f in ["size"] + CTOR_TYPES]), ty(e)),
        ),
        *call_result(
            e,
            staged_in(
                e,
                e.mb.labeled(
                    "m",
                    e.seq(
                        e.let("__p", alloc(e, e.lower(in_(e, "size")))),
                        e.call(fn_of(e, e.lower(e.v("store"))), e.tup(e.v("__p"), graft(e, a(e, "argument")))),
                        e.mb.return_to("m", pair()),
                    ),
                ),
            ),
        ),
    ]
    of = [*call_result(e, staged_in(e, e.mb.labeled("m", e.seq(e.let("__p", e.n(0)), e.mb.return_to("m", pair())))))]
    record_wasm.ctor_type(
        e, x, "cctor", "closure constructor", {"make": make, "of": of}, [("raw", ty(e)), ("vt", ty(e)), ("pt", ty(e))]
    )


def _callable_parts(e, label):
    """Host statements binding `raw` (the callable interface type of the argument's `callable`, which is the owned
    callable type), `cown` (its adopting type), `margt`, `mret`, `noarg` and the target types."""
    return [
        *const_type_arg(e, label, field(e, e.v("fields"), "callable"), "ct0"),
        *record_wasm.host_lets(e),
        e.let("owned_m", e.lower(e.fld(e.v("destructor"), "owned_m"))),
        e.let("it_m", e.lower(e.fld(e.v("iface"), "it_m"))),
        e.if_only(
            e.not_(has_b(e, xx(e), e.v("ct0"), e.v("owned_m"))),
            ret_m(
                e,
                err_cve(
                    e,
                    loc(e),
                    e.cat(e.s(label + ": callable must be the owned callable type, not "), ty_desc(e, e.v("ct0"))),
                ),
            ),
        ),
        e.let("raw", bim0(e, e.v("owned_m"), "under", e.fld(lookup(e, xx(e), e.v("ct0"), e.v("owned_m")), "value"))),
        e.let("cown", e.call(e.lower(e.fld(e.v("destructor"), "adopt")), e.v("ct0"))),
        e.if_only(
            e.not_(has_b(e, xx(e), e.v("raw"), e.v("it_m"))),
            ret_m(
                e, err_cve(e, loc(e), e.cat(e.s(label + ": callable is not an interface: "), ty_desc(e, e.v("raw"))))
            ),
        ),
        e.let("methods", bim0(e, e.v("it_m"), "methods", lookup_v(e, xx(e), e.v("raw"), e.v("it_m")))),
        e.let("n", e.rec(p("v", e.int_of(0)))),
        e.foreach(e.v("methods"), "_", e.incr(e.fld(e.v("n"), "v"))),
        e.if_only(
            e.not_(e.eq(e.fld(e.v("n"), "v"), e.int_of(1))),
            ret_m(e, err_cve(e, loc(e), label + ": callable must have exactly one method, call")),
        ),
        e.let("m", e.call_m(e.v("methods"), "get", e.int_of(0))),
        e.if_only(
            e.not_(e.eq(e.call_m(e.v("m"), "name", e.tup()), e.s("call"))),
            ret_m(e, err_cve(e, loc(e), label + ": callable's method must be call")),
        ),
        e.let("margt", e.call_m(e.v("m"), "arg", e.tup())),
        e.let("mret", e.call_m(e.v("m"), "ret", e.tup())),
        e.let("noarg", is_equal(e, xx(e), e.v("margt"), e.lower(e.v("void")))),
        e.let("pt", bim0(e, e.v("it_m"), "pt", lookup_v(e, xx(e), e.v("raw"), e.v("it_m")))),
    ]


def _ctor_out(e, kind, call_dep, destroy_dep):
    """In the staged result: the owning constructor type (destructor.owning_of over the callable's adopting type) of
    the constructor of `kind` over the vtable of the two dependency types (the call first, the destroy last) and
    the host's record and callable types."""
    vt = e.call(
        up(e, e.fld(e.v("lib"), "fnref_dep_types"), OUT_MOD),
        e.rec(p("name", e.s("closure_vtable")), p("deps", e.list_new(e.mb.eval_type(), call_dep, destroy_dep))),
    )
    inner = e.mb.as_(
        e.call(
            up(e, e.fld(e.v("cctor"), "new"), OUT_MOD),
            e.rec(
                p("kind", e.s(kind)),
                p("size", e.lower(e.v("size"))),
                p("rt", e.lower(e.v("rtt"))),
                *[p(f, e.lower(e.v(f))) for f in ["pv", "pi32", "i32", "raw", "pt"]],
                p("vt", vt),
            ),
        ),
        e.mb.eval_type(),
    )
    return e.call(
        up(e, e.fld(e.v("destructor"), "owning_of"), OUT_MOD), e.rec(p("own", e.lower(e.v("cown"))), p("new", inner))
    )


def _callable(e, x):
    """`closure.callable`: `iface.declare` of the one method `call`."""
    parts = []
    parts += argument(e, "closure.callable", "fields")
    parts += const_type_arg(e, "closure.callable", field(e, e.v("fields"), "arg"), "argt")
    parts += const_type_arg(e, "closure.callable", field(e, e.v("fields"), "ret"), "rett")
    parts.append(
        e.ret(
            const_eval_in(
                e,
                xx(e),
                loc(e),
                e.stage(
                    e.call(
                        up(e, e.fld(e.v("iface"), "declare"), BODY_MOD),
                        e.rec(
                            p(
                                "methods",
                                e.rec(p("call", e.rec(p("arg", e.lower(e.v("argt"))), p("ret", e.lower(e.v("rett")))))),
                            )
                        ),
                    )
                ),
            )
        )
    )
    const_fn(e, x, "callable_b", "closure.callable", body(e, *parts))


def _new(e, x):
    """`closure.new`: the captures' record, the destroy dependency, and (in the staged result, where the body's
    stage is a value) the call dependency over the body, the vtable and the `make` constructor.
    """
    parts = []
    parts += argument(e, "closure.new", "fields")
    parts += _callable_parts(e, "closure.new")
    parts += record_wasm.fields_parts(e, "closure.new", field(e, e.v("fields"), "capture"))
    parts.append(
        e.let(
            "call_t",
            e.if_else(
                e.v("noarg"),
                fn_type_of(e, e.lower(e.v("lib")), [e.v("rtt")], e.v("mret")),
                fn_type_of(e, e.lower(e.v("lib")), [e.v("rtt"), e.v("margt")], e.v("mret")),
            ),
        )
    )
    parts.append(e.let("dropt", record_wasm.ctor(e, "rctor", "drop", [])))
    parts.append(e.let("destroy", record_wasm.destroy_dep(e, "closure_destroy", e.v("dropt"))))
    parts.append(e.let("bodycv", field(e, e.v("fields"), "body")))
    out = e.mb.labeled(
        "__r",
        e.seq(
            e.let(
                "__cd",
                e.call(
                    up(e, e.fld(e.v("lib"), "func_dep"), OUT_MOD),
                    e.rec(
                        p("name", e.s("closure_call")),
                        p(
                            "params",
                            e.if_else(
                                e.lower(e.v("noarg")),
                                e.list_new(e.mb.types_string(), e.s("self")),
                                e.list_new(e.mb.types_string(), e.s("self"), e.s("arg")),
                            ),
                        ),
                        p("ty", e.lower(e.v("call_t"))),
                        p("body", graft(e, e.v("bodycv"))),
                    ),
                ),
            ),
            e.mb.return_to("__r", e.rec(p("make", _ctor_out(e, "make", e.v("__cd"), e.lower(e.v("destroy")))))),
        ),
    )
    parts.append(e.ret(const_eval_in(e, xx(e), loc(e), e.stage(out))))
    const_fn(e, x, "new_b", "closure.new", body(e, *parts))


def _of(e, x):
    """`closure.of`: a vtable over the plain function (checked against the callable's signature) and a no-op
    destroy; `make(())` yields the value."""
    parts = []
    parts += argument(e, "closure.of", "fields")
    parts += _callable_parts(e, "closure.of")
    parts += const_type_arg(e, "closure.of", field(e, e.v("fields"), "fn"), "fnt")
    parts.append(
        e.let("fkey", e.call(e.lower(e.fld(e.v("lib"), "dep_key")), e.rec(p("xx", xx(e)), p("dep", e.v("fnt")))))
    )
    parts.append(
        e.let(
            "expected",
            e.if_else(
                e.v("noarg"),
                fn_type_of(e, e.lower(e.v("lib")), [e.v("pv")], e.v("mret")),
                fn_type_of(e, e.lower(e.v("lib")), [e.v("pv"), e.v("margt")], e.v("mret")),
            ),
        )
    )
    parts.append(
        e.if_only(
            e.not_(is_equal(e, xx(e), e.call_m(e.v("fkey"), "fn", e.tup()), e.v("expected"))),
            ret_m(
                e,
                err_cve(
                    e,
                    loc(e),
                    e.cat(
                        e.s("closure.of: fn has type "),
                        ty_desc(e, e.call_m(e.v("fkey"), "fn", e.tup())),
                        e.s(", not "),
                        ty_desc(e, e.v("expected")),
                    ),
                ),
            ),
        )
    )
    # the static function's record type: no fields, no storage
    parts.append(e.let("size", e.int_of(0)))
    parts.append(
        e.let(
            "rtt",
            e.mb.as_(
                mk(
                    e,
                    "rt",
                    p("id", fresh_unique(e)),
                    p("caps", e.list_new(lt(e, "rfield"))),
                    p("size", e.int_of(0)),
                    p("pv", e.v("pv")),
                ),
                ty(e),
            ),
        )
    )
    parts.append(e.let("noop_t", fn_type_of(e, e.lower(e.v("lib")), [e.v("pv")], e.lower(e.v("void")))))
    out = e.mb.labeled(
        "__r",
        e.seq(
            e.let(
                "__dd",
                e.call(
                    up(e, e.fld(e.v("lib"), "func_dep"), OUT_MOD),
                    e.rec(
                        p("name", e.s("closure_noop")),
                        p("params", e.list_new(e.mb.types_string(), e.s("v"))),
                        p("ty", e.lower(e.v("noop_t"))),
                        p("body", e.stage(e.seq())),
                    ),
                ),
            ),
            e.mb.return_to("__r", e.rec(p("make", _ctor_out(e, "of", e.lower(e.v("fnt")), e.v("__dd"))))),
        ),
    )
    parts.append(e.ret(const_eval_in(e, xx(e), loc(e), e.stage(out))))
    const_fn(e, x, "of_b", "closure.of", body(e, *parts))


def _callback_of(e, x):
    """`closure.callback_of`: the reference to the callable's `call` function (its vtable's first entry) and its
    object pointer, read from its pair."""
    parts = []
    parts.append(e.let("argv", a(e, "argument")))
    parts.append(
        e.if_only(
            e.not_(record_wasm.cve_has(e, e.v("argv"))),
            ret_m(e, err_cve(e, loc(e), "closure.callback_of: argument has no value")),
        )
    )
    parts.append(e.let("ct0", cve_type(e, e.v("argv"))))
    parts.append(e.let("owned_m", e.lower(e.fld(e.v("destructor"), "owned_m"))))
    parts.append(e.let("it_m", e.lower(e.fld(e.v("iface"), "it_m"))))
    parts.append(e.let("is_owned", has_b(e, xx(e), e.v("ct0"), e.v("owned_m"))))
    parts.append(
        e.let(
            "raw",
            e.if_else(
                e.v("is_owned"),
                bim0(e, e.v("owned_m"), "under", e.fld(lookup(e, xx(e), e.v("ct0"), e.v("owned_m")), "value")),
                e.v("ct0"),
            ),
        )
    )
    parts.append(
        e.if_only(
            e.not_(has_b(e, xx(e), e.v("raw"), e.v("it_m"))),
            ret_m(e, err_cve(e, loc(e), e.cat(e.s("closure.callback_of: not a callable: "), ty_desc(e, e.v("ct0"))))),
        )
    )
    parts.append(e.let("rawcv", e.if_else(e.v("is_owned"), retag_values(e, e.v("argv"), e.v("raw")), e.v("argv"))))
    parts.append(e.let("pt", bim0(e, e.v("it_m"), "pt", lookup_v(e, xx(e), e.v("raw"), e.v("it_m")))))
    parts.append(e.let("pv", bim0(e, e.v("it_m"), "pv", lookup_v(e, xx(e), e.v("raw"), e.v("it_m")))))
    parts.append(
        e.let(
            "m",
            e.call_m(bim0(e, e.v("it_m"), "methods", lookup_v(e, xx(e), e.v("raw"), e.v("it_m"))), "get", e.int_of(0)),
        )
    )
    parts.append(e.let("margt", e.call_m(e.v("m"), "arg", e.tup())))
    parts.append(e.let("mret", e.call_m(e.v("m"), "ret", e.tup())))
    parts.append(
        e.let(
            "call_t",
            e.if_else(
                is_equal(e, xx(e), e.v("margt"), e.lower(e.v("void"))),
                fn_type_of(e, e.lower(e.v("lib")), [e.v("pv")], e.v("mret")),
                fn_type_of(e, e.lower(e.v("lib")), [e.v("pv"), e.v("margt")], e.v("mret")),
            ),
        )
    )
    parts.append(e.let("fr_t", e.call(e.lower(e.fld(e.v("lib"), "fnref")), e.v("call_t"))))
    parts.append(
        e.let(
            "pair_t", e.call(e.lower(e.fld(e.v("lib"), "tuple")), e.list_new(e.mb.eval_type(), e.v("fr_t"), e.v("pv")))
        )
    )
    parts.append(
        e.ret(
            ok_cve(
                e,
                staged_in(
                    e,
                    e.mb.labeled(
                        "c",
                        e.seq(
                            e.let("__s", e.mb.as_(graft(e, e.v("rawcv")), e.lower(e.v("pt")))),
                            e.mb.return_to(
                                "c",
                                e.mb.as_(
                                    e.tup(
                                        conv(
                                            e,
                                            up(e, e.v("int_to_fnref"), BODY_MOD),
                                            e.mb.field(e.mb.field(e.v("__s"), e.n(1)), e.n(0)),
                                            e.lower(e.v("fr_t")),
                                        ),
                                        e.mb.field(e.v("__s"), e.n(0)),
                                    ),
                                    e.lower(e.v("pair_t")),
                                ),
                            ),
                        ),
                    ),
                ),
            )
        )
    )
    const_fn(e, x, "callback_of_b", "closure.callback_of", body(e, *parts))


def module(e):
    x = []
    record_wasm.module_lets(e, x)
    x.append(e.let("iface", e.import_local("iface", iface_wasm.FILE)))
    x.append(e.let("pt", e.call(e.fld(e.v("lib"), "tuple"), e.list_new(e.mb.eval_type(), e.v("pv"), e.v("pi32")))))
    x.append(e.let("int_to_fnref", e.fld(e.v("lib"), "int_to_fnref")))
    record_wasm.rfield(e, x)
    record_wasm.rt(e, x, "closure")
    record_wasm.rctor(e, x)
    _cctor(e, x)
    _callable(e, x)
    _new(e, x)
    _of(e, x)
    _callback_of(e, x)
    x.append(e.finish(e.v("d")))
    names = ["callable", "new", "of", "callback_of"]
    x.append(e.ret(e.rec(*[p(n, e.fld(e.v(n + "_b"), "func")) for n in names])))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(*[p(n, e.fld(e.v("k"), n)) for n in names])))
    return top
