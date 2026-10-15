"""Helpers shared by the target ecosystem modules (llvm, wat, wasi, js, glsl, webidl, ...)."""

from .eco_mb import p


def ty(e):
    return e.mb.eval_type()


def str_(e):
    return e.mb.types_string()


def int_t(e):
    return e.mb.types_int()


def bool_t(e):
    return e.mb.types_bool()


def cve_t(e):
    return e.mb.types_cve()


def code_t(e):
    return e.mb.types_code()


def const_eval_in(e, xx_, staged):
    return e.call(e.mb.eval_const_eval(), e.rec(p("xx", xx_), p("staged", staged)))


def host_cve(e, staged):
    return unwrap_cve_t(e, const_eval_in(e, xx(e), staged))


def str_cve(e, str_expr):
    return host_cve(e, e.stage(e.lower(str_expr)))


def graft(e, cv):
    return e.mb.graft(cv)


def key_str(e, key):
    return e.call(e.eval_builtin("constkey_to_str"), key)


def ty_desc(e, ty_):
    return bim0(e, e.mb.eval_type(), "desc", ty_)


def count_let(e, counter):
    return e.let(counter, e.rec(p("v", e.int_of(0))))


def count_loop(e, counter, list_):
    return e.foreach(list_, "_", e.incr(e.fld(e.v(counter), "v")))


def xx_t(e):
    return e.types_expr_context()


def loc_t(e):
    return e.types_loc()


def lv(e, name):
    return e.lower_v(name)


def t(e, obj):
    return e.fld(e.v(obj), "type")


def lt(e, obj):
    return e.lower(t(e, obj))


def mk(e, obj, *fields):
    return e.call(e.lower(e.fld(e.v(obj), "new")), e.rec(*fields))


def mk_arg(e, obj, arg):
    return e.call(e.lower(e.fld(e.v(obj), "new")), arg)


def hf(e, fn, arg):
    return e.call(e.lower_v(fn), arg)


def hf_rec(e, fn, *fields):
    return hf(e, fn, e.rec(*fields))


def im0(e, iface, method, recv):
    return e.call(e.fld(lt(e, iface), method), recv)


def bim(e, iface, method, recv, arg):
    return e.call(e.fld(iface, method), e.tup(recv, arg))


def bim0(e, iface, method, recv):
    return e.call(e.fld(iface, method), recv)


def lookup(e, xx_, typ, iface_type):
    return e.call(e.mb.eval_aspect_lookup(), e.tup(typ, iface_type, xx_))


def has(e, xx_, typ, iface):
    return e.fld(lookup(e, xx_, typ, lt(e, iface)), "is_some")


def asp(e, xx_, typ, iface):
    return e.fld(lookup(e, xx_, typ, lt(e, iface)), "value")


def has_b(e, xx_, typ, iface_type):
    return e.fld(lookup(e, xx_, typ, iface_type), "is_some")


def acc(e, xx_, typ, iface, method):
    return im0(e, iface, method, asp(e, xx_, typ, iface))


def cve_value(e, cve_tp):
    return e.fld(e.call(e.fld(cve_tp, "value"), e.tup()), "value")


def cve_has(e, cve_tp):
    return e.fld(e.call(e.fld(cve_tp, "value"), e.tup()), "is_some")


def cve_ended(e, cve_tp):
    return e.call(e.fld(cve_tp, "control_ended"), e.tup())


def cve_code(e, cve_tp):
    return e.fld(cve_tp, "code")


def cve_type(e, cve_tp):
    return e.call(e.fld(e.mb.eval_value(), "type"), cve_value(e, cve_tp))


def cast_value(e, xx_, loc_, typ, cv):
    return e.call(e.eval_builtin("cast_value"), e.rec(p("xx", xx_), p("loc", loc_), p("type", typ), p("cv", cv)))


def code_none(e, loc_):
    return e.call(e.eval_builtin("code_none"), loc_)


def cv_of(e, code_tp, value):
    return e.call(e.mb.eval_codevalue(), e.rec(p("code", code_tp), p("value", value)))


def cv_no(e, code_tp):
    return e.call(e.eval_builtin("codevalue_no_value"), code_tp)


def ok_cve(e, v):
    return e.eresult_ok(e.mb.types_cve(), v)


def err_cve(e, loc_, msg):
    """`msg`: expr or plain string."""
    if isinstance(msg, str):
        msg = e.s(msg)
    return e.eresult_err(e.mb.types_cve(), loc_, msg)


def errs_t(e):
    return e.list_type(e.mb.builtin("types", "expr_err"))


def try_er(e, call, result_type):
    return e.mb.try_catch_finally(
        e.eresult_ok(result_type, call),
        ("__errs", errs_t(e), e.eresult_errs(result_type, e.v("__errs"))),
        None,
    )


def unwrap_cve_t(e, res):
    return e.match_of(res, "__r", None, p("ok", e.v("__r")), p("errs", e.mb.throw_(e.v("__r"))))


def throw_err(e, loc_, msg):
    """`msg`: expr or plain string."""
    if isinstance(msg, str):
        msg = e.s(msg)
    return e.match_of(
        err_cve(e, loc_, msg),
        "__x",
        None,
        p("ok", e.mb.panic(e.s("unreachable"))),
        p("errs", e.mb.throw_(e.v("__x"))),
    )


def panic_errs(e, target, what, errs):
    return e.seq(
        e.let("__m", e.list_new(e.mb.types_string())),
        e.foreach(errs, "__e", e.push(e.v("__m"), e.call_m(e.v("__e"), "message", e.tup()))),
        e.mb.panic(e.cat(e.s(target + ": " + what + ": "), e.join(e.v("__m"), "; "))),
    )


def must_v(e, target, res, what):
    return e.match_of(res, "__r", None, p("ok", e.v("__r")), p("errs", panic_errs(e, target, what, e.v("__r"))))


def xx(e):
    return e.fld(e.v("arg"), "xx")


def loc(e):
    return e.fld(e.v("arg"), "loc")


def a(e, *keys):
    return e.fld(e.v("arg"), *keys)


def in_(e, *keys):
    return e.fld(e.v("inner"), *keys)


def outer(e):
    return e.v("outer")


def reinterpret(e, value, obj):
    return e.call(e.mb.must_reinterpret(), e.tup(value, lt(e, obj)))


def push(e, list_, element):
    return e.push(list_, element)


def dfalse(e):
    return e.mb.as_(e.b(False), bool_t(e))


def is_const(e, xx_, typ):
    return has_b(e, xx_, typ, e.mb.eval_aspect_int())


def is_equal(e, xx_, self_, other):
    return bim(e, e.mb.eval_type(), "is_equal", self_, e.rec(p("xx", xx_), p("other", other)))


def type_aspect(e, xx_, self_, key):
    return bim(e, e.mb.eval_type(), "aspect", self_, e.rec(p("xx", xx_), p("key", key)))


def const_fn(e, out, bind, name, body_, d="d"):
    """A const function (`define.const_func`): `body_` runs when the caller compiles, with `arg` = {xx, loc,
    argument} and an eresult(cve) result, so staged code inside it sees the caller's values."""
    out.append(e.let(bind, e.call_m(e.v(d), "const_func", e.s(name))))
    out.append(
        e.call_m(
            e.v(bind),
            "impl",
            e.rec(
                p("impl_body", e.stage(body_)),
                p("exception_type", e.mb.opt_none_type()),
                p("description", e.opt_none(str_(e))),
            ),
        )
    )


def code_seq(e, *codes):
    """The target's sequence of the host code values `codes`: an eresult(code)."""
    return bim(
        e,
        e.mb.eval_target(),
        "seq",
        e.fld(xx(e), "target"),
        e.rec(p("loc", loc(e)), p("entries", e.list_new(code_t(e), *codes))),
    )


def call_result(e, result_expr):
    """Statements ending a function `call` body: return the code-value `result_expr`, with the callee's own code
    (`self`, which a field access may have given hoisted code) run first."""
    return [
        e.let("__r", result_expr),
        e.let(
            "__c",
            unwrap_m(e, code_seq(e, cve_code(e, a(e, "self")), cve_code(e, e.v("__r"))), e.mb.types_cve()),
        ),
        ret_m(
            e,
            ok_cve(
                e,
                e.if_else(
                    cve_has(e, e.v("__r")),
                    cv_of(e, e.v("__c"), cve_value(e, e.v("__r"))),
                    cv_no(e, e.v("__c")),
                ),
            ),
        ),
    ]


def target_drop_body(e):
    """Target `drop`: emit the value type's drop aspect when the value has one."""
    none = e.eresult_ok(code_t(e), code_none(e, loc(e)))
    return body(
        e,
        e.if_only(e.not_(cve_has(e, a(e, "cv"))), ret_m(e, none)),
        e.let("asp", lookup(e, xx(e), cve_type(e, a(e, "cv")), e.mb.eval_aspect_drop_dynamic())),
        e.if_only(
            e.fld(e.v("asp"), "is_some"),
            ret_m(
                e,
                bim(
                    e,
                    e.mb.eval_aspect_drop_dynamic(),
                    "drop",
                    e.fld(e.v("asp"), "value"),
                    e.rec(p("xx", xx(e)), p("loc", loc(e)), p("cv", a(e, "cv"))),
                ),
            ),
        ),
        e.ret(none),
    )


def binding_drop_body(e):
    """Binding `drop`: consume the binding's value and drop it through the target."""
    used = bim(
        e,
        e.mb.eval_binding(),
        "use",
        outer(e),
        e.rec(
            p("xx", xx(e)),
            p("loc", loc(e)),
            p("setter", e.call(e.mb.eval_binding_setter_consumed(), e.tup())),
            p("code", code_none(e, loc(e))),
        ),
    )
    return e.call(e.mb.eval_drop_value(), e.rec(p("xx", xx(e)), p("loc", loc(e)), p("cv", used)))


def type_can_cast_from(e, xx_, loc_, self_, src):
    return bim(e, e.mb.eval_type(), "can_cast_from", self_, e.rec(p("xx", xx_), p("loc", loc_), p("source_type", src)))


def to_str(e, v):
    return e.to_str(v)


def num(e, v):
    return e.n(v)


def op_id(e, op_):
    return e.eval_builtin("aspect_operator_" + op_ + "_id")


def op_iface(e, op_):
    return e.eval_builtin("operator_" + op_)


def asp_id(e, name):
    return e.eval_builtin("aspect_" + name + "_id")


def asp_iface(e, name):
    return e.eval_builtin("aspect_" + name)


def def_iface(e, out, name, *methods):
    out.append(e.let(name, e.call_m0(e.v("d"), "interface")))
    out.append(e.interface_impl(e.v(name), True))
    out.append(e.let(name + "_id", e.call_m0(e.v(name), "aspect_id")))
    for key, value in methods:
        out.append(
            e.call_m(
                e.v(name),
                "func",
                e.rec(p("name", e.s(key)), p("arg", e.tup()), p("ret", e.option_type_some(value))),
            )
        )


def def_obj(e, out, name, desc, inner_type):
    out.append(e.let(name, e.def_object(e.v("d"), desc)))
    out.append(e.object_impl(e.v(name), inner_type))


def method(e, out, obj, name, arg_type, ret, body_):
    out.append(e.method_impl(e.v(obj), name, arg_type, e.option_type_some(ret), e.stage(body_)))


def ret_m(e, value):
    return e.mb.return_to("m", value)


def body(e, *exprs):
    seq = e.seq(*exprs)
    if not returns_to(seq, "m"):
        return seq
    return e.mb.labeled("m", seq)


def returns_to(expr, label):
    """True if `expr` contains a `return` to `label` not shadowed by an inner `labeled` of the same name."""
    ((kind, v),) = expr["variant"].items()
    if kind == "as":
        return returns_to(v["base"], label) or returns_to(v["target"], label)
    if kind == "bind":
        return returns_to(v["name"], label) or returns_to(v["value"], label)
    if kind == "call":
        return returns_to(v["func"], label) or returns_to(v["arg"], label)
    if kind == "field":
        return returns_to(v["base"], label) or returns_to(v["key"], label)
    if kind == "foreach":
        return returns_to(v["base"], label) or returns_to(v["element_key"], label) or returns_to(v["body"], label)
    if kind in ("graft", "lower", "stage", "loop"):
        return returns_to(v, label)
    if kind == "if":
        for branch in v["conditions"]:
            if returns_to(branch["condition"], label) or returns_to(branch["body"], label):
                return True
        return _returns_to_opt(v["fallback"], label)
    if kind == "labeled":
        return v["label"] != label and returns_to(v["inner"], label)
    if kind == "literal":
        return False
    if kind == "match":
        if returns_to(v["base"], label) or returns_to(v["element_key"], label):
            return True
        for branch in v["cases"]:
            if returns_to(branch["condition"], label) or returns_to(branch["body"], label):
                return True
        return _returns_to_opt(v["fallback"], label)
    if kind == "operator_binary":
        return returns_to(v["base"], label) or returns_to(v["reference"], label)
    if kind == "operator_unary":
        return returns_to(v["base"], label)
    if kind == "record":
        for entry in v:
            if returns_to(entry["key"], label) or returns_to(entry["value"], label):
                return True
        return False
    if kind == "return":
        return v["label"].get("some") == label or _returns_to_opt(v["value"], label)
    if kind == "scope_use":
        return returns_to(v, label)
    if kind in ("seq", "tuple"):
        return any(returns_to(x, label) for x in v)
    if kind == "set":
        return returns_to(v["base"], label) or returns_to(v["value"], label)
    if kind == "try":
        if returns_to(v["body"], label) or _returns_to_opt(v["finally_block"], label):
            return True
        if "none" in v["catch_clause"]:
            return False
        c = v["catch_clause"]["some"]
        return (
            returns_to(c["binding_name"], label)
            or returns_to(c["exception_type"], label)
            or returns_to(c["body"], label)
        )
    raise AssertionError(kind)


def _returns_to_opt(opt, label):
    return "some" in opt and returns_to(opt["some"], label)


def unwrap_m(e, res, ret_inner):
    return e.match_of(res, "__r", None, p("ok", e.v("__r")), p("errs", ret_m(e, e.eresult_errs(ret_inner, e.v("__r")))))


def unwrap_cve_m(e, res):
    return unwrap_m(e, res, e.mb.types_cve())


def and_b(e, a_, b_):
    return e.if_else(a_, b_, e.b(False))


def or_b(e, a_, b_):
    return e.if_else(e.not_(a_), b_, e.b(True))


def is_target_code(e, code_tp):
    return e.eq(e.match_of(code_tp, "__c", None, p("none", e.int_of(0)), p("target", e.int_of(1))), e.int_of(1))


def fn_def(e, out, target, name, arg_type, ret):
    out.append(e.let(name + "_b", e.def_func(e.v("d"), target + "." + name)))
    out.append(e.let(name, e.fld(e.v(name + "_b"), "func")))
    e.fn_sigs[name] = [arg_type, e.option_type_some(ret), e.option_type_none()]
    return e.v(name)


def fn_impl(e, out, name, body_expr):
    sig = e.fn_sigs.pop(name)
    out.append(e.func_impl(e.v(name + "_b"), sig[0], sig[1], sig[2], e.stage(body_expr)))


def fn_throws(e, name, exception_type):
    e.fn_sigs[name][2] = e.option_type_some(exception_type)


def accessor(e, x, obj, field, typ):
    method(e, x, obj, field, e.tup(), typ, in_(e, field))


def p_(e, key):
    return e.fld(e.v("p"), key)


def self_type(e, x, obj, desc, dispatch, can_cast_from, cast_from, can_cast_to, cast_to, is_equal_):
    x.append(e.impl_interface(e.v(obj), asp_iface(e, "type"), p("type", body(e, e.ret(outer(e))))))
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_type(),
            p("desc", desc),
            p(
                "exporter",
                e.opt_some(
                    e.mb.builtin("eval", "artifact_exporter"),
                    e.call(e.eval_builtin("source_object_exporter"), e.lower(t(e, obj))),
                ),
            ),
            p("aspect", dispatch),
            p("can_cast_from", can_cast_from),
            p("cast_from", cast_from),
            p("can_cast_to", can_cast_to),
            p("cast_to", cast_to),
            p("is_equal", is_equal_),
        )
    )


def no_cast_to(e):
    return e.mb.as_(e.b(False), bool_t(e))


def cast_to_panic(e):
    return e.mb.panic(e.s("cast_to unreachable"))


def src_type(e):
    return a(e, "source_type")


def src_bits(e, marker):
    return acc(e, xx(e), src_type(e), marker, "bits")


def cv_bits(e, st, marker):
    return acc(e, xx(e), st, marker, "bits")


def op(e, x, obj, op_, body_expr):
    x.append(e.impl_interface(e.v(obj), op_iface(e, op_), p(op_, body(e, e.ret(body_expr)))))


def marker_type(e, x, obj, desc, marker, dispatch):
    self_type(
        e,
        x,
        obj,
        e.s(desc),
        dispatch,
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), marker))),
    )


def voc_t(e):
    return e.mb.builtin("types", "value_object_const")


def lookup_v(e, xx_, typ, iface_type):
    return e.fld(lookup(e, xx_, typ, iface_type), "value")


def rt_branch(e, id_, value):
    return (e.mb.operator_eq(e.fld(e.v("arg"), "key"), id_), value)


def rt_dispatch(e, under_type, inner):
    delegated = [
        e.mb.eval_aspect_bind_dynamic_id(),
        e.mb.eval_aspect_consume_dynamic_id(),
        e.mb.eval_aspect_drop_dynamic_id(),
    ]
    branches = []
    for own in ["lift", "bind", "initial_bind", "field_use_dynamic", "artifact"]:
        branches.append(rt_branch(e, asp_id(e, own), e.opt_some(e.mb.types_aspect(), outer(e))))
    for id_ in delegated:
        branches.append(rt_branch(e, id_, type_aspect(e, xx(e), under_type, a(e, "key"))))
    return e.mb.if_of(branches, inner)


def unit_t(e):
    """The language's unit type, `()`."""
    return e.call(e.mb.builtin("types", "tuple"), e.list_new(e.mb.eval_type()))


def fn_of(e, type_):
    """The function value of the callable type `type_` (a constant where this is evaluated): the unit cast to it."""
    return e.mb.as_(e.tup(), type_)


def can_cast_from_unit(e):
    """`can_cast_from` of a callable type: only the unit casts to it."""
    return body(e, e.ret(is_equal(e, xx(e), unit_t(e), src_type(e))))


def cast_from_empty(e):
    """`cast_from` of a callable type: the unit becomes the type's empty value, its function."""
    return body(
        e,
        e.ret(ok_cve(e, cv_of(e, code_none(e, loc(e)), e.call(e.eval_builtin("value_empty"), outer(e))))),
    )


def def_empty_binding(e, x, obj, desc):
    """A binding of an empty value: using it yields the empty value of the stored type, dropping it is nothing."""
    def_obj(e, x, obj, desc, e.rec(p("ty", ty(e))))
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_binding(),
            p("use", cv_of(e, code_none(e, loc(e)), e.call(e.eval_builtin("value_empty"), in_(e, "ty")))),
            p("drop", e.eresult_ok(e.mb.types_code(), code_none(e, loc(e)))),
            p("fork", outer(e)),
            p("merge", e.eresult_ok(e.mb.eval_binding(), outer(e))),
        )
    )


def bind_empty(e, binding_obj):
    """Aspect `bind` of a type whose values are empty: the binding holds the type."""
    return e.eresult_ok(
        e.mb.types_bind_result(),
        e.call(
            e.mb.eval_bind_result(),
            e.rec(p("code", code_none(e, loc(e))), p("binding", mk(e, binding_obj, p("ty", outer(e))))),
        ),
    )


def dep_type(e, x, obj, desc, fields, h_fn, with_argument, binding_obj):
    """A dependency as a callable type: its function value (the unit cast to it) calls the host function `h_fn` with
    the stored `fields` (name first), and the call's argument when `with_argument`."""
    def_iface(e, x, obj + "_m", p("name", str_(e)))
    def_obj(e, x, obj, desc, e.rec(*[p(f, ft) for f, ft in fields]))
    x.append(e.impl_interface(e.v(obj), t(e, obj + "_m"), p("name", in_(e, "name"))))
    self_type(
        e,
        x,
        obj,
        e.cat(e.s(desc + " "), in_(e, "name")),
        e.aspect_dispatch(asp_id(e, "function"), asp_id(e, "bind")),
        can_cast_from_unit(e),
        cast_from_empty(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), obj + "_m"),
                    e.eq(in_(e, "name"), acc(e, xx(e), a(e, "other"), obj + "_m", "name")),
                )
            ),
        ),
    )
    h_args = [p("xx", xx(e)), p("loc", loc(e))] + [p(f, in_(e, f)) for f, _ in fields]
    if with_argument:
        h_args.append(p("argument", a(e, "argument")))
    x.append(
        e.impl_interface(
            e.v(obj),
            asp_iface(e, "function"),
            p("call", body(e, e.ret(try_er(e, hf_rec(e, h_fn, *h_args), cve_t(e))))),
            p("exception_type", e.option_type_lowered_none()),
        )
    )
    x.append(e.impl_interface(e.v(obj), e.mb.eval_aspect_bind(), p("bind", bind_empty(e, binding_obj))))


def can_cast_from_self(e):
    return body(e, e.ret(is_equal(e, xx(e), outer(e), src_type(e))))


def cast_from_self(e):
    return body(e, e.ret(ok_cve(e, a(e, "cv"))))


def structural_exits(e):
    return [
        p("source_value", body(e, e.ret(ok_cve(e, a(e, "cv"))))),
        p(
            "exit_value",
            body(
                e,
                e.ret(
                    e.eresult_ok(
                        e.mb.types_exit_value(),
                        e.call(e.mb.eval_exit_value(), e.rec(p("carries", e.b(False)), p("cv", a(e, "cv")))),
                    )
                ),
            ),
        ),
    ]


def is_runtime(e, cv):
    return bim(
        e,
        e.mb.eval_target(),
        "value_is_runtime",
        e.fld(xx(e), "target"),
        e.rec(p("xx", xx(e)), p("value", cve_value(e, cv))),
    )


def retag_runtime(e, cv, type_):
    return cv_of(
        e,
        cve_code(e, cv),
        e.call(
            e.eval_builtin("value_dynamic"),
            e.rec(
                p(
                    "source",
                    e.fld(
                        e.call(
                            e.mb.must_reinterpret(), e.tup(cve_value(e, cv), e.mb.builtin("types", "value_dynamic"))
                        ),
                        "source",
                    ),
                ),
                p("type", type_),
            ),
        ),
    )


def tag_value(e, cv, type_):
    return e.if_else(
        is_runtime(e, cv),
        ok_cve(e, retag_runtime(e, cv, type_)),
        ok_cve(
            e,
            cv_of(
                e,
                code_none(e, loc(e)),
                e.call(
                    e.eval_builtin("value_object_const"),
                    e.rec(
                        p("type", type_),
                        p("data", e.fld(e.call(e.mb.must_reinterpret(), e.tup(cve_value(e, cv), voc_t(e))), "data")),
                    ),
                ),
            ),
        ),
    )


def rt_lift_impl(e, x, obj):
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_lift(),
            p(
                "lift",
                e.eresult_ok(
                    e.mb.eval_value(),
                    e.call(
                        e.eval_builtin("value_object_const"),
                        e.rec(p("type", outer(e)), p("data", a(e, "external_host_value"))),
                    ),
                ),
            ),
        )
    )


def rt_bind_impl(e, x, obj, under_type):
    x.append(
        e.impl_interface(
            e.v(obj),
            asp_iface(e, "artifact"),
            p("exporter", e.call(e.eval_builtin("exporter_object_const"), under_type)),
        )
    )
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_bind(),
            p(
                "bind",
                bim(
                    e,
                    e.mb.eval_aspect_bind(),
                    "bind",
                    lookup_v(e, xx(e), under_type, e.mb.eval_aspect_bind()),
                    e.rec(p("xx", xx(e)), p("loc", loc(e)), p("cv", a(e, "cv"))),
                ),
            ),
        )
    )


def rt_use_impl(e, x, obj):
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_field_use_dynamic(),
            p(
                "field_use_dynamic",
                ok_cve(
                    e,
                    cv_of(
                        e,
                        code_none(e, loc(e)),
                        e.call(
                            e.eval_builtin("value_dynamic"), e.rec(p("source", a(e, "source")), p("type", outer(e)))
                        ),
                    ),
                ),
            ),
        )
    )
    # A parameter slot of the dynamic target: the binding over that slot, typed as this type.
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_initial_bind(),
            p(
                "initial_bind",
                e.eresult_ok(
                    e.mb.eval_binding(),
                    e.call(
                        e.eval_builtin("binding_dynamic"),
                        e.rec(
                            p(
                                "dynamic_key",
                                e.fld(
                                    e.call(
                                        e.mb.must_reinterpret(), e.tup(a(e, "slot"), e.mb.eval_binding_slot_dynamic())
                                    ),
                                    "id",
                                ),
                            ),
                            p("type", outer(e)),
                        ),
                    ),
                ),
            ),
        )
    )


def ident_of(e, s):
    """`s` with every byte outside [A-Za-z0-9_] replaced by `_`: a name usable in emitted wat or llvm."""

    def in_range(n, lo, hi):
        return and_b(e, e.mb.operator_ge(n, num(e, ord(lo))), e.mb.operator_le(n, num(e, ord(hi))))

    n = e.mb.as_(e.v("__b"), int_t(e))
    ok = or_b(
        e,
        or_b(e, in_range(n, "a", "z"), in_range(n, "A", "Z")),
        or_b(e, in_range(n, "0", "9"), e.eq(n, num(e, ord("_")))),
    )
    return e.mb.labeled(
        "ident",
        e.seq(
            e.let("__out", e.list_new(e.mb.types_byte())),
            e.foreach(
                e.call(e.mb.eval_str_utf8(), s),
                "__b",
                e.if_else(
                    ok,
                    push(e, e.v("__out"), e.v("__b")),
                    e.foreach(e.call(e.mb.eval_str_utf8(), e.s("_")), "__u", push(e, e.v("__out"), e.v("__u"))),
                ),
            ),
            e.mb.return_to(
                "ident",
                e.match_of(
                    e.call(e.eval_builtin("str_from_utf8"), e.v("__out")),
                    "__s",
                    None,
                    p("some", e.v("__s")),
                    p("none", e.mb.panic(e.s("ident_of: bytes are not valid UTF-8"))),
                ),
            ),
        ),
    )


def const_type_arg(e, label, cv, bind):
    """Binds `bind` to the constant type the code-value `cv` holds, else errors out of the const function."""
    return [
        e.let(bind + "_tk", lookup(e, xx(e), cve_type(e, cv), asp_iface(e, "type"))),
        e.if_only(
            or_b(e, is_runtime(e, cv), e.not_(e.fld(e.v(bind + "_tk"), "is_some"))),
            ret_m(e, err_cve(e, loc(e), label + ": " + bind + " must be a constant type")),
        ),
        e.let(bind, bim(e, asp_iface(e, "type"), "type", e.fld(e.v(bind + "_tk"), "value"), cve_value(e, cv))),
    ]


def method_fields(e, x, obj, meth_obj, methods):
    """`field` on `obj` values: each name in `methods` yields a bound method, a value of the callable type `meth_obj`
    (fields `op`, the name, and `self`, the receiver) whose call runs the operation."""
    x.append(
        e.impl_interface(
            e.v(obj),
            asp_iface(e, "field"),
            p(
                "field",
                body(
                    e,
                    e.let("sk", lookup(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
                    e.if_only(
                        e.not_(e.fld(e.v("sk"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "the field name must be a constant string")),
                    ),
                    e.let(
                        "key",
                        bim(
                            e,
                            e.mb.eval_aspect_string_const(),
                            "get",
                            e.fld(e.v("sk"), "value"),
                            cve_value(e, a(e, "key")),
                        ),
                    ),
                    *[
                        e.if_only(
                            e.eq(e.v("key"), e.s(m)),
                            ret_m(
                                e,
                                ok_cve(
                                    e,
                                    cv_of(
                                        e,
                                        cve_code(e, a(e, "self")),
                                        e.call(
                                            e.eval_builtin("value_object_const"),
                                            e.rec(
                                                p(
                                                    "type",
                                                    mk(
                                                        e,
                                                        meth_obj,
                                                        p("op", e.s(m)),
                                                        p(
                                                            "self",
                                                            cv_of(e, code_none(e, loc(e)), cve_value(e, a(e, "self"))),
                                                        ),
                                                    ),
                                                ),
                                                p("data", e.tup()),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        )
                        for m in methods
                    ],
                    e.ret(err_cve(e, loc(e), e.cat(e.s("no field "), e.v("key")))),
                ),
            ),
            p("type_opt", e.option_type_lowered_none()),
            p("keys", e.list_new(e.mb.types_constkey(), *[e.mb.as_(e.s(k), e.mb.types_constkey()) for k in methods])),
        )
    )


def method_type(e, x, obj, desc):
    """A bound method's type: `{op, self}`, callable (its `function` aspect is implemented by the caller)."""
    def_obj(e, x, obj, desc, e.rec(p("op", str_(e)), p("self", cve_t(e))))
    no = e.mb.as_(e.b(False), bool_t(e))
    self_type(
        e,
        x,
        obj,
        e.cat(e.s(desc + " "), in_(e, "op")),
        e.aspect_dispatch(asp_id(e, "function")),
        no,
        cast_to_panic(e),
        no,
        cast_to_panic(e),
        no,
    )


def is_const_expr(expr):
    """Whether the staged expression `expr` is a constant: a literal, a lowered value, or arithmetic over those."""
    ((kind, v),) = expr["variant"].items()
    if kind in ("literal", "lower"):
        return True
    if kind == "operator_binary":
        return is_const_expr(v["base"]) and is_const_expr(v["reference"])
    if kind == "operator_unary":
        return is_const_expr(v["base"])
    return False


def int_as(e, n, type_):
    """The integer expression `n` as the integer type `type_`: a constant casts (range-checked by the target), a
    runtime value wraps (`wrap`)."""
    if is_const_expr(n):
        return e.mb.as_(n, type_)
    return e.call(e.fld(n, "wrap"), type_)
