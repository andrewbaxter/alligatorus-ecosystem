"""lifetimes.atz: lifetime-ordered references, checked at drop sites in one pass.

`lifetimes.set({name, count})` makes a lifetime set: a total order of `count` levels where a lower level lives longer.
From a set, `s.own(T)` is the owner type over `T` (bind an owner to track its lifetime) and `s.at({index, under})`
is the reference type `L<index>(under)`: a reference whose referent is promised to live at least as long as level
`index`, so it may only point at owners of level `index` or lower (longer-lived).

An owner's binding starts with no level. Loading it yields a reference with an unassigned level that acts as `under`
everywhere; converting that reference to `L<i>(under)` (an `as`, a typed `let`, a call argument) assigns level `i` to
the owner's binding, once (a different level later is a compile error). Every level-carrying binding, owner or
reference, counts as live until it is dropped. Dropping an owner of level `i` while anything of a higher level is still
alive is a compile error: a shorter-lived reference could still point at it. References may be dropped at any time.
Checks happen at each drop site as the compiler reaches it, so one pass suffices.

Branches: the compiler forks every binding per branch and merges afterwards, and emits each exit path's cleanup by
dropping the forked bindings speculatively. The set therefore keeps one live table per fork generation: a fork burst
(the forks of one branch) copies its source generation's table, events in a branch only touch that branch's table,
and a merge continues from the table of a branch that did not drop the merged binding (one that did had exited).

Owners and references have the runtime representation of `under` (they are retagged values).
"""

from ..core import values
from ..eco_mb import p
from ..target_mb import (
    a,
    acc,
    and_b,
    asp_id,
    asp_iface,
    bim,
    bim0,
    body,
    bool_t,
    cast_from_self,
    cast_to_panic,
    cast_value,
    code_none,
    code_t,
    cve_has,
    cve_t,
    cve_value,
    def_iface,
    def_obj,
    err_cve,
    errs_t,
    fn_def,
    fn_impl,
    fn_throws,
    has,
    hf_rec,
    in_,
    int_t,
    is_equal,
    loc,
    lookup,
    lv,
    method,
    mk,
    must_v,
    ok_cve,
    outer,
    reinterpret,
    ret_m,
    self_type,
    str_,
    t,
    throw_err,
    to_str,
    try_er,
    ty,
    ty_desc,
    type_aspect,
    unwrap_m,
    xx,
)

FILE = "lifetimes.atz"

TARGET = "lifetimes"


def _binding_t(e):
    return e.mb.eval_binding()


def _setter_t(e):
    return e.mb.builtin("eval", "binding_setter")


def _live_t(e):
    """One live count: the fork generation, the level and the number of live bindings carrying it there."""
    return e.rec(p("gen", int_t(e)), p("level", int_t(e)), p("n", int_t(e)))


def _lkey(e, gen, level):
    return e.cat(to_str(e, gen), e.s(":"), to_str(e, level))


def _rec_xl(e, *fields):
    return e.rec(p("xx", xx(e)), p("loc", loc(e)), *fields)


def _retag(e, cv, type_):
    return hf_rec(e, "h_retag", p("xx", xx(e)), p("loc", loc(e)), p("cv", cv), p("type", type_))


def _retag_v(e, cv, type_):
    return must_v(e, TARGET, try_er(e, _retag(e, cv, type_), cve_t(e)), "retag binding value")


def _retag_m(e, cv, type_, ret_inner):
    return unwrap_m(e, try_er(e, _retag(e, cv, type_), cve_t(e)), ret_inner)


def _setter_set(e, setter, binding, drop_modified):
    return bim(e, _setter_t(e), "set", setter, _rec_xl(e, p("new_binding", binding), p("drop_modified", drop_modified)))


def _binding_use(e, binding, setter, code):
    return bim(e, _binding_t(e), "use", binding, _rec_xl(e, p("setter", setter), p("code", code)))


def _dispatch(e, own_ids, fallback):
    branches = []
    for id_ in own_ids:
        branches.append((e.eq(a(e, "key"), id_), e.opt_some(e.mb.types_aspect(), outer(e))))
    return e.mb.if_of(branches, fallback)


def _lbinding(e, inner, lown, level, gen, id_, set_):
    return mk(
        e,
        "lbinding",
        p("inner", inner),
        p("lown", lown),
        p("level", level),
        p("gen", gen),
        p("id", id_),
        p("set", set_),
    )


def _latb(e, inner, lat, gen, id_, set_):
    return mk(e, "latb", p("inner", inner), p("lat", lat), p("gen", gen), p("id", id_), p("set", set_))


def _own_set(e, lown):
    return acc(e, xx(e), lown, "lown_m", "set")


def _own_under(e, lown):
    return acc(e, xx(e), lown, "lown_m", "under")


def _at_set(e, lat):
    return acc(e, xx(e), lat, "lat_m", "set")


def _at_level(e, lat):
    return acc(e, xx(e), lat, "lat_m", "level")


def _at_under(e, lat):
    return acc(e, xx(e), lat, "lat_m", "under")


def _same_set(e, s1, s2):
    return e.eq(e.call_m(s1, "name", e.tup()), e.call_m(s2, "name", e.tup()))


def _acquire(e, set_, gen, level):
    return e.call_m(set_, "acquire", e.rec(p("gen", gen), p("level", level)))


def _release_m(e, set_, gen, level, id_, check, ret_inner):
    return unwrap_m(
        e,
        e.call_m(
            set_, "release", e.rec(p("loc", loc(e)), p("gen", gen), p("level", level), p("id", id_), p("check", check))
        ),
        ret_inner,
    )


def _event(e, set_, gen):
    return e.seq(e.let("__ev", e.call_m(set_, "event", gen)))


def _merge_gen(e, set_, self_gen, self_id, others, obj):
    """Statements binding `mgen`, the generation a merged binding continues in: from a branch that did not drop it,
    this one first."""
    return [
        e.let("cands", e.list_new(int_t(e))),
        e.push(e.v("cands"), self_gen),
        e.foreach(others, "o", e.push(e.v("cands"), e.call_m(reinterpret(e, e.v("o"), obj), "gen", e.tup()))),
        e.let("mgen", e.call_m(set_, "merge_gen", e.rec(p("gens", e.v("cands")), p("id", self_id)))),
    ]


def _host_fns(e, x):
    def xl():
        return [p("xx", e.types_expr_context()), p("loc", e.types_loc())]

    fn_def(e, x, TARGET, "h_retag", e.rec(*xl(), p("cv", cve_t(e)), p("type", ty(e))), cve_t(e))
    fn_throws(e, "h_retag", errs_t(e))
    fn_impl(
        e,
        x,
        "h_retag",
        body(
            e,
            e.let("v", cve_value(e, a(e, "cv"))),
            e.match_of(
                e.call(e.mb.reinterpret(), e.tup(loc(e), e.v("v"), e.mb.builtin("types", "value_dynamic"))),
                "__d",
                None,
                p(
                    "ok",
                    ret_m(
                        e,
                        e.call(
                            e.mb.eval_codevalue(),
                            e.rec(
                                p("code", e.fld(a(e, "cv"), "code")),
                                p(
                                    "value",
                                    e.call(
                                        e.eval_builtin("value_dynamic"),
                                        e.rec(p("source", e.fld(e.v("__d"), "source")), p("type", a(e, "type"))),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
                p("errs", e.seq()),
            ),
            e.match_of(
                e.call(e.mb.reinterpret(), e.tup(loc(e), e.v("v"), e.lower(e.fld(e.v("values"), "retag")))),
                "__t",
                None,
                p(
                    "ok",
                    ret_m(
                        e,
                        e.call(
                            e.mb.eval_codevalue(),
                            e.rec(
                                p("code", e.fld(a(e, "cv"), "code")),
                                p(
                                    "value",
                                    bim(e, e.lower(e.fld(e.v("values"), "retag")), "retag", e.v("__t"), a(e, "type")),
                                ),
                            ),
                        ),
                    ),
                ),
                p("errs", throw_err(e, loc(e), "lifetimes: only runtime values can carry a lifetime")),
            ),
        ),
    )


def _lset(e, x):
    """The set object: a name (sets are compared by name), the level count, the live counts per generation and
    level, the dropped marks per (generation, binding), and the fork/merge burst state."""
    for f, ft in [("name", str_(e)), ("count", int_t(e)), ("live", e.map_type(str_(e), _live_t(e)))]:
        x.append(e.method_impl(e.v("lset"), f, e.tup(), e.option_type_some(ft), e.stage(in_(e, f))))
    method(
        e, x, "lset", "own", ty(e), ty(e), e.mb.as_(mk(e, "lown", p("set", outer(e)), p("under", e.v("arg"))), ty(e))
    )
    method(
        e,
        x,
        "lset",
        "at",
        e.rec(p("index", int_t(e)), p("under", ty(e))),
        ty(e),
        e.seq(
            e.if_only(
                e.mb.operator_lt(a(e, "index"), e.int_of(0)),
                e.mb.panic(e.cat(e.s("lifetimes: level "), to_str(e, a(e, "index")), e.s(" is negative"))),
            ),
            e.if_only(
                e.mb.operator_ge(a(e, "index"), in_(e, "count")),
                e.mb.panic(
                    e.cat(
                        e.s("lifetimes: level "),
                        to_str(e, a(e, "index")),
                        e.s(" is beyond the set's "),
                        to_str(e, in_(e, "count")),
                        e.s(" levels"),
                    )
                ),
            ),
            e.ret(
                e.mb.as_(mk(e, "lat", p("set", outer(e)), p("level", a(e, "index")), p("under", a(e, "under"))), ty(e))
            ),
        ),
    )
    # event(gen): a use, drop, bind or count change in generation `gen` closes any open fork/merge burst and makes
    # `gen` current (new bindings join the current generation).
    method(
        e,
        x,
        "lset",
        "event",
        int_t(e),
        int_t(e),
        e.seq(
            e.mb.set(in_(e, "open_fork_src"), e.int_of(-1)),
            e.mb.set(in_(e, "open_merge"), e.int_of(-1)),
            e.mb.set(in_(e, "cur"), e.v("arg")),
            e.ret(e.v("arg")),
        ),
    )
    method(e, x, "lset", "cur_gen", e.tup(), int_t(e), in_(e, "cur"))
    method(
        e,
        x,
        "lset",
        "next_id",
        e.tup(),
        int_t(e),
        e.seq(e.mb.set(in_(e, "ids"), e.mb.operator_add(in_(e, "ids"), e.int_of(1))), e.ret(in_(e, "ids"))),
    )
    # copy_gen(src): a new generation starting from `src`'s table.
    method(
        e,
        x,
        "lset",
        "copy_gen",
        int_t(e),
        int_t(e),
        e.seq(
            e.mb.set(in_(e, "gens"), e.mb.operator_add(in_(e, "gens"), e.int_of(1))),
            e.let("g", in_(e, "gens")),
            e.let("adds", e.list_new(_live_t(e))),
            e.foreach(
                in_(e, "live"),
                "en",
                e.seq(
                    e.let("v", e.fld(e.v("en"), "value")),
                    e.if_only(
                        e.eq(e.fld(e.v("v"), "gen"), e.v("arg")),
                        e.push(
                            e.v("adds"),
                            e.rec(
                                p("gen", e.v("g")), p("level", e.fld(e.v("v"), "level")), p("n", e.fld(e.v("v"), "n"))
                            ),
                        ),
                    ),
                ),
            ),
            e.foreach(
                e.v("adds"),
                "ad",
                e.call_m(in_(e, "live"), "put", e.tup(_lkey(e, e.v("g"), e.fld(e.v("ad"), "level")), e.v("ad"))),
            ),
            e.ret(e.v("g")),
        ),
    )
    # fork_gen(src): the generation a fork of a `src` binding joins. The forks of one branch arrive in a burst
    # with no events between them, so they share one generation.
    method(
        e,
        x,
        "lset",
        "fork_gen",
        int_t(e),
        int_t(e),
        e.seq(
            e.if_only(e.eq(in_(e, "open_fork_src"), e.v("arg")), e.ret(in_(e, "open_fork_gen"))),
            e.let("g", e.call_m(outer(e), "copy_gen", e.v("arg"))),
            e.mb.set(in_(e, "open_fork_src"), e.v("arg")),
            e.mb.set(in_(e, "open_fork_gen"), e.v("g")),
            e.mb.set(in_(e, "open_merge"), e.int_of(-1)),
            e.mb.set(in_(e, "cur"), e.v("g")),
            e.ret(e.v("g")),
        ),
    )
    # merge_gen({gens, id}): the generation a merge continues in: copied from the first candidate generation that
    # did not drop binding `id` (a branch that dropped it exited); the merges of one join share one generation.
    method(
        e,
        x,
        "lset",
        "merge_gen",
        e.rec(p("gens", e.list_type(int_t(e))), p("id", int_t(e))),
        int_t(e),
        e.seq(
            e.if_only(e.not_(e.eq(in_(e, "open_merge"), e.int_of(-1))), e.ret(in_(e, "open_merge"))),
            e.let("pick", e.rec(p("g", e.int_of(-1)))),
            e.foreach(
                a(e, "gens"),
                "g0",
                e.if_only(
                    e.eq(e.fld(e.v("pick"), "g"), e.int_of(-1)),
                    e.if_only(
                        e.not_(e.call_m(in_(e, "dropped"), "has", _lkey(e, e.v("g0"), a(e, "id")))),
                        e.mb.set(e.fld(e.v("pick"), "g"), e.v("g0")),
                    ),
                ),
            ),
            e.foreach(
                a(e, "gens"),
                "g1",
                e.if_only(e.eq(e.fld(e.v("pick"), "g"), e.int_of(-1)), e.mb.set(e.fld(e.v("pick"), "g"), e.v("g1"))),
            ),
            e.let("g", e.call_m(outer(e), "copy_gen", e.fld(e.v("pick"), "g"))),
            e.mb.set(in_(e, "open_merge"), e.v("g")),
            e.mb.set(in_(e, "open_fork_src"), e.int_of(-1)),
            e.mb.set(in_(e, "cur"), e.v("g")),
            e.ret(e.v("g")),
        ),
    )
    # acquire({gen, level}): one more live binding at `level` in `gen`; yields the new count.
    method(
        e,
        x,
        "lset",
        "acquire",
        e.rec(p("gen", int_t(e)), p("level", int_t(e))),
        int_t(e),
        e.seq(
            e.let("__ev", e.call_m(outer(e), "event", a(e, "gen"))),
            e.let("k", _lkey(e, a(e, "gen"), a(e, "level"))),
            e.if_only(
                e.not_(e.call_m(in_(e, "live"), "has", e.v("k"))),
                e.call_m(
                    in_(e, "live"),
                    "put",
                    e.tup(e.v("k"), e.rec(p("gen", a(e, "gen")), p("level", a(e, "level")), p("n", e.int_of(0)))),
                ),
            ),
            e.let("n", e.mb.operator_add(e.fld(e.call_m(in_(e, "live"), "get", e.v("k")), "n"), e.int_of(1))),
            e.call_m(
                in_(e, "live"),
                "put",
                e.tup(e.v("k"), e.rec(p("gen", a(e, "gen")), p("level", a(e, "level")), p("n", e.v("n")))),
            ),
            e.ret(e.v("n")),
        ),
    )
    # release({loc, gen, level, id, check}): binding `id` at `level` is dropped in `gen`; with `check` (an owner),
    # anything live at a higher level in that generation is a lifetime violation.
    eres_int = e.call(e.mb.types_eresult(), e.mb.types_int_box())
    method(
        e,
        x,
        "lset",
        "release",
        e.rec(
            p("loc", e.types_loc()), p("gen", int_t(e)), p("level", int_t(e)), p("id", int_t(e)), p("check", bool_t(e))
        ),
        eres_int,
        e.mb.labeled(
            "m",
            e.seq(
                e.let("__ev", e.call_m(outer(e), "event", a(e, "gen"))),
                e.call_m(in_(e, "dropped"), "put", e.tup(_lkey(e, a(e, "gen"), a(e, "id")), e.int_of(1))),
                e.foreach(
                    in_(e, "live"),
                    "en",
                    e.seq(
                        e.let("v", e.fld(e.v("en"), "value")),
                        e.if_only(
                            and_b(
                                e,
                                a(e, "check"),
                                and_b(
                                    e,
                                    e.eq(e.fld(e.v("v"), "gen"), a(e, "gen")),
                                    and_b(
                                        e,
                                        e.mb.operator_gt(e.fld(e.v("v"), "level"), a(e, "level")),
                                        e.mb.operator_gt(e.fld(e.v("v"), "n"), e.int_of(0)),
                                    ),
                                ),
                            ),
                            e.mb.return_to(
                                "m",
                                e.eresult_err(
                                    e.mb.types_int_box(),
                                    a(e, "loc"),
                                    e.cat(
                                        e.s("lifetime "),
                                        in_(e, "name"),
                                        e.s(": an owner of level "),
                                        to_str(e, a(e, "level")),
                                        e.s(" is dropped while a value of level "),
                                        to_str(e, e.fld(e.v("v"), "level")),
                                        e.s(" is still alive"),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
                e.let("k", _lkey(e, a(e, "gen"), a(e, "level"))),
                e.let("n", e.mb.operator_sub(e.fld(e.call_m(in_(e, "live"), "get", e.v("k")), "n"), e.int_of(1))),
                e.call_m(
                    in_(e, "live"),
                    "put",
                    e.tup(e.v("k"), e.rec(p("gen", a(e, "gen")), p("level", a(e, "level")), p("n", e.v("n")))),
                ),
                e.mb.return_to("m", e.eresult_ok(e.mb.types_int_box(), e.v("n"))),
            ),
        ),
    )
    fn_def(e, x, TARGET, "c_set", e.rec(p("name", str_(e)), p("count", int_t(e))), t(e, "lset"))
    fn_impl(
        e,
        x,
        "c_set",
        body(
            e,
            e.if_only(
                e.mb.operator_lt(a(e, "count"), e.int_of(1)),
                e.mb.panic(e.s("lifetimes.set: count must be at least 1")),
            ),
            e.ret(
                mk(
                    e,
                    "lset",
                    p("name", a(e, "name")),
                    p("count", a(e, "count")),
                    p("live", e.map_new(str_(e), _live_t(e))),
                    p("dropped", e.map_new(str_(e), e.mb.types_int_box())),
                    p("gens", e.int_of(0)),
                    p("cur", e.int_of(0)),
                    p("ids", e.int_of(0)),
                    p("open_fork_src", e.int_of(-1)),
                    p("open_fork_gen", e.int_of(-1)),
                    p("open_merge", e.int_of(-1)),
                )
            ),
        ),
    )


def _lown(e, x):
    """The owner type: binds to a level-tracking binding; its reference is `luref`."""
    br_t = e.mb.types_bind_result()
    x.append(e.impl_interface(e.v("lown"), t(e, "lown_m"), p("set", in_(e, "set")), p("under", in_(e, "under"))))
    self_type(
        e,
        x,
        "lown",
        e.cat(e.s("lifetime owner "), ty_desc(e, in_(e, "under"))),
        _dispatch(
            e,
            [
                asp_id(e, "bind"),
                asp_id(e, "initial_bind"),
                e.mb.eval_aspect_drop_dynamic_id(),
                asp_id(e, "function"),
                lv(e, "lown_m_id"),
            ],
            type_aspect(e, xx(e), in_(e, "under"), a(e, "key")),
        ),
        body(e, e.ret(is_equal(e, xx(e), outer(e), a(e, "source_type")))),
        cast_from_self(e),
        e.mb.as_(e.b(True), bool_t(e)),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), a(e, "dest_type")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.ret(
                err_cve(
                    e,
                    loc(e),
                    e.cat(
                        e.s("lifetime owner used as "),
                        ty_desc(e, a(e, "dest_type")),
                        e.s(": bind it, then borrow it through the binding"),
                    ),
                )
            ),
        ),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "lown_m"),
                    and_b(
                        e,
                        _same_set(e, in_(e, "set"), _own_set(e, a(e, "other"))),
                        is_equal(e, xx(e), in_(e, "under"), _own_under(e, a(e, "other"))),
                    ),
                )
            ),
        ),
    )
    # Calling the type converts an `under` value into an owner value.
    x.append(
        e.impl_interface(
            e.v("lown"),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    e.if_only(
                        e.not_(cve_has(e, a(e, "argument"))),
                        ret_m(e, err_cve(e, loc(e), "lifetime owner: argument has no value")),
                    ),
                    e.let(
                        "v",
                        unwrap_m(e, cast_value(e, xx(e), loc(e), in_(e, "under"), a(e, "argument")), cve_t(e)),
                    ),
                    e.ret(ok_cve(e, _retag_m(e, e.v("v"), outer(e), cve_t(e)))),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )
    x.append(
        e.impl_interface(
            e.v("lown"),
            e.mb.eval_aspect_bind(),
            p(
                "bind",
                body(
                    e,
                    e.let("ub", lookup(e, xx(e), in_(e, "under"), e.mb.eval_aspect_bind())),
                    e.if_only(
                        e.not_(e.fld(e.v("ub"), "is_some")),
                        ret_m(
                            e,
                            e.eresult_err(
                                br_t,
                                loc(e),
                                e.cat(e.s("lifetimes: "), ty_desc(e, in_(e, "under")), e.s(" cannot be bound")),
                            ),
                        ),
                    ),
                    e.let("v", _retag_m(e, a(e, "cv"), in_(e, "under"), br_t)),
                    e.let(
                        "r",
                        unwrap_m(
                            e,
                            bim(
                                e,
                                e.mb.eval_aspect_bind(),
                                "bind",
                                e.fld(e.v("ub"), "value"),
                                _rec_xl(e, p("cv", e.v("v"))),
                            ),
                            br_t,
                        ),
                    ),
                    e.ret(
                        e.eresult_ok(
                            br_t,
                            e.call(
                                e.mb.eval_bind_result(),
                                e.rec(
                                    p("code", e.fld(e.v("r"), "code")),
                                    p(
                                        "binding",
                                        _lbinding(
                                            e,
                                            e.fld(e.v("r"), "binding"),
                                            outer(e),
                                            e.int_of(-1),
                                            e.call_m(in_(e, "set"), "cur_gen", e.tup()),
                                            e.call_m(in_(e, "set"), "next_id", e.tup()),
                                            in_(e, "set"),
                                        ),
                                    ),
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    )
    # A parameter slot: the under type's binding over it, tracked like a bound owner.
    x.append(
        e.impl_interface(
            e.v("lown"),
            e.mb.eval_aspect_initial_bind(),
            p(
                "initial_bind",
                body(
                    e,
                    e.let("ui", lookup(e, xx(e), in_(e, "under"), e.mb.eval_aspect_initial_bind())),
                    e.if_only(
                        e.not_(e.fld(e.v("ui"), "is_some")),
                        ret_m(
                            e,
                            e.eresult_err(
                                _binding_t(e),
                                loc(e),
                                e.cat(e.s("lifetimes: "), ty_desc(e, in_(e, "under")), e.s(" cannot be a parameter")),
                            ),
                        ),
                    ),
                    e.let(
                        "r",
                        unwrap_m(
                            e,
                            bim(
                                e,
                                e.mb.eval_aspect_initial_bind(),
                                "initial_bind",
                                e.fld(e.v("ui"), "value"),
                                _rec_xl(e, p("slot", a(e, "slot"))),
                            ),
                            _binding_t(e),
                        ),
                    ),
                    e.ret(
                        e.eresult_ok(
                            _binding_t(e),
                            _lbinding(
                                e,
                                e.v("r"),
                                outer(e),
                                e.int_of(-1),
                                e.call_m(in_(e, "set"), "cur_gen", e.tup()),
                                e.call_m(in_(e, "set"), "next_id", e.tup()),
                                in_(e, "set"),
                            ),
                        )
                    ),
                ),
            ),
        )
    )
    # An owner value outside a binding carries no level: dropping it drops the `under` value.
    x.append(
        e.impl_interface(
            e.v("lown"),
            e.mb.eval_aspect_drop_dynamic(),
            p(
                "drop",
                body(
                    e,
                    e.let("v", _retag_m(e, a(e, "cv"), in_(e, "under"), code_t(e))),
                    e.ret(e.call(e.mb.eval_drop_value(), _rec_xl(e, p("cv", e.v("v"))))),
                ),
            ),
        )
    )


def _lbinding_impl(e, x):
    def set_():
        return in_(e, "set")

    x.append(
        e.impl_interface(
            e.v("lbinding"),
            _binding_t(e),
            p(
                "use",
                e.seq(
                    _event(e, set_(), in_(e, "gen")),
                    e.ret(
                        _retag_v(
                            e,
                            _binding_use(
                                e,
                                in_(e, "inner"),
                                mk(
                                    e,
                                    "lsetter",
                                    p("setter", a(e, "setter")),
                                    p("lown", in_(e, "lown")),
                                    p("level", in_(e, "level")),
                                    p("gen", in_(e, "gen")),
                                    p("id", in_(e, "id")),
                                    p("set", in_(e, "set")),
                                ),
                                a(e, "code"),
                            ),
                            mk(
                                e,
                                "luref",
                                p("lown", in_(e, "lown")),
                                p("inner", in_(e, "inner")),
                                p("setter", a(e, "setter")),
                                p("level", in_(e, "level")),
                                p("gen", in_(e, "gen")),
                                p("id", in_(e, "id")),
                                p("set", in_(e, "set")),
                            ),
                        )
                    ),
                ),
            ),
            p(
                "drop",
                body(
                    e,
                    e.if_else(
                        e.mb.operator_ge(in_(e, "level"), e.int_of(0)),
                        e.seq(
                            e.let(
                                "__n",
                                _release_m(
                                    e, set_(), in_(e, "gen"), in_(e, "level"), in_(e, "id"), e.b(True), code_t(e)
                                ),
                            )
                        ),
                        _event(e, set_(), in_(e, "gen")),
                    ),
                    e.ret(bim(e, _binding_t(e), "drop", in_(e, "inner"), _rec_xl(e))),
                ),
            ),
            p(
                "fork",
                _lbinding(
                    e,
                    bim0(e, _binding_t(e), "fork", in_(e, "inner")),
                    in_(e, "lown"),
                    in_(e, "level"),
                    e.call_m(set_(), "fork_gen", in_(e, "gen")),
                    in_(e, "id"),
                    set_(),
                ),
            ),
            p(
                "merge",
                body(
                    e,
                    e.let("inners", e.list_new(_binding_t(e))),
                    e.foreach(
                        a(e, "others"),
                        "o",
                        e.seq(
                            e.let("ob", reinterpret(e, e.v("o"), "lbinding")),
                            e.if_only(
                                e.not_(e.eq(e.call_m(e.v("ob"), "level", e.tup()), in_(e, "level"))),
                                ret_m(
                                    e,
                                    e.eresult_err(
                                        _binding_t(e),
                                        loc(e),
                                        e.s("lifetime level assigned differently across branches"),
                                    ),
                                ),
                            ),
                            e.push(e.v("inners"), e.call_m(e.v("ob"), "inner", e.tup())),
                        ),
                    ),
                    *_merge_gen(e, set_(), in_(e, "gen"), in_(e, "id"), a(e, "others"), "lbinding"),
                    e.let(
                        "m",
                        unwrap_m(
                            e,
                            bim(e, _binding_t(e), "merge", in_(e, "inner"), _rec_xl(e, p("others", e.v("inners")))),
                            _binding_t(e),
                        ),
                    ),
                    e.ret(
                        e.eresult_ok(
                            _binding_t(e),
                            _lbinding(e, e.v("m"), in_(e, "lown"), in_(e, "level"), e.v("mgen"), in_(e, "id"), set_()),
                        )
                    ),
                ),
            ),
        )
    )
    x.append(
        e.impl_interface(
            e.v("lsetter"),
            _setter_t(e),
            p(
                "set",
                _setter_set(
                    e,
                    in_(e, "setter"),
                    _lbinding(
                        e,
                        a(e, "new_binding"),
                        in_(e, "lown"),
                        in_(e, "level"),
                        in_(e, "gen"),
                        in_(e, "id"),
                        in_(e, "set"),
                    ),
                    a(e, "drop_modified"),
                ),
            ),
        )
    )


def _luref(e, x):
    """A reference loaded from an owner binding: acts as `under`; converting it to `L<i>` assigns the level."""

    def under():
        return _own_under(e, in_(e, "lown"))

    def is_at(dest):
        return and_b(
            e,
            has(e, xx(e), dest, "lat_m"),
            and_b(
                e,
                _same_set(e, _own_set(e, in_(e, "lown")), _at_set(e, dest)),
                is_equal(e, xx(e), under(), _at_under(e, dest)),
            ),
        )

    x.append(
        e.impl_interface(
            e.v("luref"),
            t(e, "luref_m"),
            p("lown", in_(e, "lown")),
            p("inner", in_(e, "inner")),
            p("setter", in_(e, "setter")),
            p("level", in_(e, "level")),
            p("gen", in_(e, "gen")),
            p("id", in_(e, "id")),
            p("set", in_(e, "set")),
        )
    )
    self_type(
        e,
        x,
        "luref",
        e.cat(e.s("reference to "), ty_desc(e, in_(e, "lown"))),
        _dispatch(
            e,
            [asp_id(e, "field"), e.mb.eval_aspect_drop_dynamic_id(), asp_id(e, "bind"), lv(e, "luref_m_id")],
            type_aspect(e, xx(e), under(), a(e, "key")),
        ),
        e.mb.as_(e.b(False), bool_t(e)),
        cast_to_panic(e),
        e.if_else(
            is_at(a(e, "dest_type")),
            e.mb.as_(e.b(True), bool_t(e)),
            bim(e, e.mb.eval_type(), "can_cast_to", under(), _rec_xl(e, p("dest_type", a(e, "dest_type")))),
        ),
        body(
            e,
            e.if_only(
                is_at(a(e, "dest_type")),
                e.seq(
                    e.let("lvl", _at_level(e, a(e, "dest_type"))),
                    e.if_only(
                        and_b(
                            e,
                            e.mb.operator_ge(in_(e, "level"), e.int_of(0)),
                            e.not_(e.eq(in_(e, "level"), e.v("lvl"))),
                        ),
                        ret_m(
                            e,
                            err_cve(
                                e,
                                loc(e),
                                e.cat(
                                    e.s("lifetime: this owner already has level "),
                                    to_str(e, in_(e, "level")),
                                    e.s(", it cannot also be level "),
                                    to_str(e, e.v("lvl")),
                                ),
                            ),
                        ),
                    ),
                    e.if_only(
                        e.mb.operator_lt(in_(e, "level"), e.int_of(0)),
                        e.seq(
                            e.let(
                                "__set",
                                _setter_set(
                                    e,
                                    in_(e, "setter"),
                                    _lbinding(
                                        e,
                                        in_(e, "inner"),
                                        in_(e, "lown"),
                                        e.v("lvl"),
                                        in_(e, "gen"),
                                        in_(e, "id"),
                                        in_(e, "set"),
                                    ),
                                    e.b(True),
                                ),
                            ),
                            e.let("__n", _acquire(e, in_(e, "set"), in_(e, "gen"), e.v("lvl"))),
                        ),
                    ),
                    ret_m(e, ok_cve(e, _retag_m(e, a(e, "cv"), a(e, "dest_type"), cve_t(e)))),
                ),
            ),
            e.let("v", _retag_m(e, a(e, "cv"), under(), cve_t(e))),
            e.ret(
                bim(
                    e,
                    e.mb.eval_type(),
                    "cast_to",
                    under(),
                    _rec_xl(e, p("cv", e.v("v")), p("dest_type", a(e, "dest_type"))),
                )
            ),
        ),
        is_equal(e, xx(e), under(), a(e, "other")),
    )
    _ref_field(e, x, "luref", under, lambda xx_: acc(e, xx_, in_(e, "lown"), "lown_m", "under"))
    x.append(
        e.impl_interface(
            e.v("luref"),
            e.mb.eval_aspect_bind(),
            p(
                "bind",
                e.eresult_err(
                    e.mb.types_bind_result(),
                    loc(e),
                    e.s("a lifetime reference cannot be bound as is; convert it to a level type first"),
                ),
            ),
        )
    )
    x.append(
        e.impl_interface(
            e.v("luref"), e.mb.eval_aspect_drop_dynamic(), p("drop", e.eresult_ok(code_t(e), code_none(e, loc(e))))
        )
    )


def _ref_field(e, x, obj, under, under_x):
    """Field access on a reference: the `under` type's field aspect over the retagged value. `under_x(xx)` names
    the under type from an explicit context (the `keys` method receives the context alone)."""
    x.append(
        e.impl_interface(
            e.v(obj),
            asp_iface(e, "field"),
            p(
                "field",
                body(
                    e,
                    e.let("uf", lookup(e, xx(e), under(), asp_iface(e, "field"))),
                    e.if_only(
                        e.not_(e.fld(e.v("uf"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "lifetime reference: the value has no fields")),
                    ),
                    e.let("v", _retag_m(e, a(e, "self"), under(), cve_t(e))),
                    e.ret(
                        bim(
                            e,
                            asp_iface(e, "field"),
                            "field",
                            e.fld(e.v("uf"), "value"),
                            _rec_xl(e, p("self", e.v("v")), p("key", a(e, "key"))),
                        )
                    ),
                ),
            ),
            p(
                "type_opt",
                body(
                    e,
                    e.let("uf", lookup(e, xx(e), under(), asp_iface(e, "field"))),
                    e.if_only(e.not_(e.fld(e.v("uf"), "is_some")), ret_m(e, e.option_type_lowered_none())),
                    e.ret(
                        bim(
                            e,
                            asp_iface(e, "field"),
                            "type_opt",
                            e.fld(e.v("uf"), "value"),
                            e.rec(p("xx", xx(e)), p("key", a(e, "key"))),
                        )
                    ),
                ),
            ),
            # keys takes the context alone, so here `arg` is the context.
            p(
                "keys",
                body(
                    e,
                    e.let("uf", lookup(e, e.v("arg"), under_x(e.v("arg")), asp_iface(e, "field"))),
                    e.if_only(e.not_(e.fld(e.v("uf"), "is_some")), ret_m(e, e.list_new(e.mb.types_constkey()))),
                    e.ret(bim(e, asp_iface(e, "field"), "keys", e.fld(e.v("uf"), "value"), e.v("arg"))),
                ),
            ),
        )
    )


def _lat(e, x):
    """`L<i>(under)`: a reference of level i; binding one counts as live at that level until it is dropped."""
    br_t = e.mb.types_bind_result()

    def under():
        return in_(e, "under")

    x.append(
        e.impl_interface(
            e.v("lat"), t(e, "lat_m"), p("set", in_(e, "set")), p("level", in_(e, "level")), p("under", in_(e, "under"))
        )
    )
    self_type(
        e,
        x,
        "lat",
        e.cat(e.s("L"), to_str(e, in_(e, "level")), e.s(" "), ty_desc(e, in_(e, "under"))),
        _dispatch(
            e,
            [
                asp_id(e, "field"),
                asp_id(e, "bind"),
                asp_id(e, "initial_bind"),
                e.mb.eval_aspect_drop_dynamic_id(),
                lv(e, "lat_m_id"),
            ],
            type_aspect(e, xx(e), under(), a(e, "key")),
        ),
        body(e, e.ret(is_equal(e, xx(e), outer(e), a(e, "source_type")))),
        cast_from_self(e),
        e.if_else(
            is_equal(e, xx(e), outer(e), a(e, "dest_type")),
            e.mb.as_(e.b(True), bool_t(e)),
            bim(e, e.mb.eval_type(), "can_cast_to", under(), _rec_xl(e, p("dest_type", a(e, "dest_type")))),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), a(e, "dest_type")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.let("v", _retag_m(e, a(e, "cv"), under(), cve_t(e))),
            e.ret(
                bim(
                    e,
                    e.mb.eval_type(),
                    "cast_to",
                    under(),
                    _rec_xl(e, p("cv", e.v("v")), p("dest_type", a(e, "dest_type"))),
                )
            ),
        ),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "lat_m"),
                    and_b(
                        e,
                        _same_set(e, in_(e, "set"), _at_set(e, a(e, "other"))),
                        and_b(
                            e,
                            e.eq(in_(e, "level"), _at_level(e, a(e, "other"))),
                            is_equal(e, xx(e), under(), _at_under(e, a(e, "other"))),
                        ),
                    ),
                )
            ),
        ),
    )
    _ref_field(e, x, "lat", under, lambda xx_: in_(e, "under"))
    x.append(
        e.impl_interface(
            e.v("lat"),
            e.mb.eval_aspect_bind(),
            p(
                "bind",
                body(
                    e,
                    e.let("ub", lookup(e, xx(e), under(), e.mb.eval_aspect_bind())),
                    e.if_only(
                        e.not_(e.fld(e.v("ub"), "is_some")),
                        ret_m(
                            e,
                            e.eresult_err(
                                br_t, loc(e), e.cat(e.s("lifetimes: "), ty_desc(e, under()), e.s(" cannot be bound"))
                            ),
                        ),
                    ),
                    e.let("v", _retag_m(e, a(e, "cv"), under(), br_t)),
                    e.let(
                        "r",
                        unwrap_m(
                            e,
                            bim(
                                e,
                                e.mb.eval_aspect_bind(),
                                "bind",
                                e.fld(e.v("ub"), "value"),
                                _rec_xl(e, p("cv", e.v("v"))),
                            ),
                            br_t,
                        ),
                    ),
                    e.let("gen", e.call_m(in_(e, "set"), "cur_gen", e.tup())),
                    e.let("__n", _acquire(e, in_(e, "set"), e.v("gen"), in_(e, "level"))),
                    e.ret(
                        e.eresult_ok(
                            br_t,
                            e.call(
                                e.mb.eval_bind_result(),
                                e.rec(
                                    p("code", e.fld(e.v("r"), "code")),
                                    p(
                                        "binding",
                                        _latb(
                                            e,
                                            e.fld(e.v("r"), "binding"),
                                            outer(e),
                                            e.v("gen"),
                                            e.call_m(in_(e, "set"), "next_id", e.tup()),
                                            in_(e, "set"),
                                        ),
                                    ),
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    )
    # A parameter slot: the under type's binding over it, live at this level until the parameter drops.
    x.append(
        e.impl_interface(
            e.v("lat"),
            e.mb.eval_aspect_initial_bind(),
            p(
                "initial_bind",
                body(
                    e,
                    e.let("ui", lookup(e, xx(e), under(), e.mb.eval_aspect_initial_bind())),
                    e.if_only(
                        e.not_(e.fld(e.v("ui"), "is_some")),
                        ret_m(
                            e,
                            e.eresult_err(
                                _binding_t(e),
                                loc(e),
                                e.cat(e.s("lifetimes: "), ty_desc(e, under()), e.s(" cannot be a parameter")),
                            ),
                        ),
                    ),
                    e.let(
                        "r",
                        unwrap_m(
                            e,
                            bim(
                                e,
                                e.mb.eval_aspect_initial_bind(),
                                "initial_bind",
                                e.fld(e.v("ui"), "value"),
                                _rec_xl(e, p("slot", a(e, "slot"))),
                            ),
                            _binding_t(e),
                        ),
                    ),
                    e.let("gen", e.call_m(in_(e, "set"), "cur_gen", e.tup())),
                    e.let("__n", _acquire(e, in_(e, "set"), e.v("gen"), in_(e, "level"))),
                    e.ret(
                        e.eresult_ok(
                            _binding_t(e),
                            _latb(
                                e,
                                e.v("r"),
                                outer(e),
                                e.v("gen"),
                                e.call_m(in_(e, "set"), "next_id", e.tup()),
                                in_(e, "set"),
                            ),
                        )
                    ),
                ),
            ),
        )
    )
    # A reference value outside a binding (a temporary) carries no live count of its own.
    x.append(
        e.impl_interface(
            e.v("lat"),
            e.mb.eval_aspect_drop_dynamic(),
            p(
                "drop",
                body(
                    e,
                    e.let("v", _retag_m(e, a(e, "cv"), under(), code_t(e))),
                    e.ret(e.call(e.mb.eval_drop_value(), _rec_xl(e, p("cv", e.v("v"))))),
                ),
            ),
        )
    )

    def lat_set():
        return in_(e, "set")

    x.append(
        e.impl_interface(
            e.v("latb"),
            _binding_t(e),
            p(
                "use",
                e.seq(
                    _event(e, lat_set(), in_(e, "gen")),
                    e.ret(
                        _retag_v(
                            e,
                            _binding_use(
                                e,
                                in_(e, "inner"),
                                mk(
                                    e,
                                    "latsetter",
                                    p("setter", a(e, "setter")),
                                    p("lat", in_(e, "lat")),
                                    p("gen", in_(e, "gen")),
                                    p("id", in_(e, "id")),
                                    p("set", in_(e, "set")),
                                ),
                                a(e, "code"),
                            ),
                            in_(e, "lat"),
                        )
                    ),
                ),
            ),
            p(
                "drop",
                body(
                    e,
                    e.let(
                        "__n",
                        _release_m(
                            e,
                            lat_set(),
                            in_(e, "gen"),
                            _at_level(e, in_(e, "lat")),
                            in_(e, "id"),
                            e.b(False),
                            code_t(e),
                        ),
                    ),
                    e.ret(bim(e, _binding_t(e), "drop", in_(e, "inner"), _rec_xl(e))),
                ),
            ),
            p(
                "fork",
                _latb(
                    e,
                    bim0(e, _binding_t(e), "fork", in_(e, "inner")),
                    in_(e, "lat"),
                    e.call_m(lat_set(), "fork_gen", in_(e, "gen")),
                    in_(e, "id"),
                    lat_set(),
                ),
            ),
            p(
                "merge",
                body(
                    e,
                    e.let("inners", e.list_new(_binding_t(e))),
                    e.foreach(
                        a(e, "others"),
                        "o",
                        e.push(e.v("inners"), e.call_m(reinterpret(e, e.v("o"), "latb"), "inner", e.tup())),
                    ),
                    *_merge_gen(e, lat_set(), in_(e, "gen"), in_(e, "id"), a(e, "others"), "latb"),
                    e.let(
                        "m",
                        unwrap_m(
                            e,
                            bim(e, _binding_t(e), "merge", in_(e, "inner"), _rec_xl(e, p("others", e.v("inners")))),
                            _binding_t(e),
                        ),
                    ),
                    e.ret(
                        e.eresult_ok(
                            _binding_t(e), _latb(e, e.v("m"), in_(e, "lat"), e.v("mgen"), in_(e, "id"), lat_set())
                        )
                    ),
                ),
            ),
        )
    )
    x.append(
        e.impl_interface(
            e.v("latsetter"),
            _setter_t(e),
            p(
                "set",
                _setter_set(
                    e,
                    in_(e, "setter"),
                    _latb(e, a(e, "new_binding"), in_(e, "lat"), in_(e, "gen"), in_(e, "id"), in_(e, "set")),
                    a(e, "drop_modified"),
                ),
            ),
        )
    )


def module(e):
    x = []
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    def_obj(
        e,
        x,
        "lset",
        "lifetime set",
        e.rec(
            p("name", str_(e)),
            p("count", int_t(e)),
            p("live", e.map_type(str_(e), _live_t(e))),
            p("dropped", e.map_type(str_(e), e.mb.types_int_box())),
            p("gens", int_t(e)),
            p("cur", int_t(e)),
            p("ids", int_t(e)),
            p("open_fork_src", int_t(e)),
            p("open_fork_gen", int_t(e)),
            p("open_merge", int_t(e)),
        ),
    )
    gen_id = [p("gen", int_t(e)), p("id", int_t(e)), p("set", t(e, "lset"))]
    def_iface(e, x, "lown_m", p("set", t(e, "lset")), p("under", ty(e)))
    def_iface(e, x, "lat_m", p("set", t(e, "lset")), p("level", int_t(e)), p("under", ty(e)))
    def_iface(
        e,
        x,
        "luref_m",
        p("lown", ty(e)),
        p("inner", _binding_t(e)),
        p("setter", _setter_t(e)),
        p("level", int_t(e)),
        *gen_id,
    )
    def_obj(e, x, "lown", "lifetime owner type", e.rec(p("set", t(e, "lset")), p("under", ty(e))))
    def_obj(
        e,
        x,
        "lbinding",
        "lifetime owner binding",
        e.rec(p("inner", _binding_t(e)), p("lown", ty(e)), p("level", int_t(e)), *gen_id),
    )
    def_obj(
        e,
        x,
        "lsetter",
        "lifetime owner binding setter",
        e.rec(p("setter", _setter_t(e)), p("lown", ty(e)), p("level", int_t(e)), *gen_id),
    )
    def_obj(
        e,
        x,
        "luref",
        "lifetime reference type",
        e.rec(p("lown", ty(e)), p("inner", _binding_t(e)), p("setter", _setter_t(e)), p("level", int_t(e)), *gen_id),
    )
    def_obj(e, x, "lat", "lifetime level type", e.rec(p("set", t(e, "lset")), p("level", int_t(e)), p("under", ty(e))))
    def_obj(e, x, "latb", "lifetime level binding", e.rec(p("inner", _binding_t(e)), p("lat", ty(e)), *gen_id))
    def_obj(
        e, x, "latsetter", "lifetime level binding setter", e.rec(p("setter", _setter_t(e)), p("lat", ty(e)), *gen_id)
    )
    for f, ft in [("inner", _binding_t(e)), ("level", int_t(e)), ("gen", int_t(e))]:
        x.append(e.method_impl(e.v("lbinding"), f, e.tup(), e.option_type_some(ft), e.stage(in_(e, f))))
    for f, ft in [("inner", _binding_t(e)), ("gen", int_t(e))]:
        x.append(e.method_impl(e.v("latb"), f, e.tup(), e.option_type_some(ft), e.stage(in_(e, f))))
    _lset(e, x)
    _host_fns(e, x)
    _lown(e, x)
    _lbinding_impl(e, x)
    _luref(e, x)
    _lat(e, x)
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("set", e.fld(e.v("c_set_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("set", e.fld(e.v("k"), "set")))))
    return top
