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


def as_object(e, value):
    """`value` as a plain host object (a const value's data)."""
    return e.call(e.mb.must_reinterpret(), e.tup(value, e.mb.builtin("types", "object")))


def recv_of(e):
    """In a bound method's `call`: the receiver, the code value stored as the method value's data."""
    data = e.fld(e.call(e.mb.must_reinterpret(), e.tup(cve_value(e, a(e, "self")), voc_t(e))), "data")
    return e.call(e.mb.must_reinterpret(), e.tup(data, cve_t(e)))


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


def unique_t(e):
    return e.mb.types_unique()


def fresh_unique(e):
    """A fresh identity. Definitions and dependencies are keyed by one, never by a name: names are hints."""
    return e.call(e.eval_builtin("fresh_unique"), e.tup())


def module_defs(e, x, defobj, desc):
    """The record a target module keeps per definition it made for an identity: `{id, ref}`, `ref` the symbol."""
    def_obj(e, x, defobj, desc, e.rec(p("id", unique_t(e)), p("ref", str_(e))))
    accessor(e, x, defobj, "id", unique_t(e))
    accessor(e, x, defobj, "ref", str_(e))


def module_defs_methods(e, x, mod, defobj):
    """On a target module holding `defs` (a list of `defobj`) and counting with `fresh_n`: `mint(hint)` yields a
    fresh module-unique symbol name `<ident>.<n>` (the hint only makes the output readable, so two definers with one
    hint never collide); `def_ref(id)` yields the symbol defined for `id`, none when the module has none; and
    `def_add({id, ref})` records one, yielding `ref`."""
    method(
        e,
        x,
        mod,
        "mint",
        str_(e),
        str_(e),
        e.cat(ident_of(e, e.v("arg")), e.s("."), to_str(e, e.call_m(outer(e), "fresh_n", e.tup()))),
    )
    method(
        e,
        x,
        mod,
        "def_ref",
        unique_t(e),
        e.call(e.mb.types_option(), str_(e)),
        e.seq(
            e.let("hit", e.rec(p("v", e.opt_none(str_(e))))),
            e.foreach(
                in_(e, "defs"),
                "d0",
                e.if_only(
                    e.eq(e.call_m(e.v("d0"), "id", e.tup()), e.v("arg")),
                    e.mb.set(e.fld(e.v("hit"), "v"), e.opt_some(str_(e), e.call_m(e.v("d0"), "ref", e.tup()))),
                ),
            ),
            e.ret(e.fld(e.v("hit"), "v")),
        ),
    )
    method(
        e,
        x,
        mod,
        "def_add",
        e.rec(p("id", unique_t(e)), p("ref", str_(e))),
        str_(e),
        e.seq(
            push(e, in_(e, "defs"), mk(e, defobj, p("id", a(e, "id")), p("ref", a(e, "ref")))),
            e.ret(a(e, "ref")),
        ),
    )


def def_once(e, mod, id_, define):
    """The symbol `mod` defines for the identity `id_`: the one already recorded, else `define` (an expression
    yielding the new symbol) recorded under `id_`."""
    return e.match_of(
        e.call_m(mod, "def_ref", id_),
        "__d",
        None,
        p("some", e.v("__d")),
        p("none", e.call_m(mod, "def_add", e.rec(p("id", id_), p("ref", define)))),
    )


def named_conv(e, x, bind, name, src_ok, to_ok, make):
    """A named conversion as a const function `{value, to}`: `make(cv, to)` (an eresult(cve)) when the value's type
    satisfies `src_ok` and the constant type `to` satisfies `to_ok`, else an error naming both. The unsafe
    conversions (pointer to pointer, pointer to integer, integer to pointer) are these: `as` never does them."""
    const_fn(
        e,
        x,
        bind,
        name,
        body(
            e,
            e.let("argv", a(e, "argument")),
            e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), name + ": argument has no value"))),
            e.let("rk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "record"))),
            e.if_only(
                e.not_(e.fld(e.v("rk"), "is_some")),
                ret_m(e, err_cve(e, loc(e), name + ": argument must be {value, to}")),
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
            e.let("valuecv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("value")))),
            e.if_only(
                e.not_(cve_has(e, e.v("valuecv"))), ret_m(e, err_cve(e, loc(e), name + ": value has no value"))
            ),
            *const_type_arg(e, name, unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("to"))), "to"),
            e.let("st", cve_type(e, e.v("valuecv"))),
            e.if_only(
                e.not_(and_b(e, src_ok(e.v("st")), to_ok(e.v("to")))),
                ret_m(
                    e,
                    err_cve(
                        e,
                        loc(e),
                        e.cat(
                            e.s(name + ": no conversion from "),
                            ty_desc(e, e.v("st")),
                            e.s(" to "),
                            ty_desc(e, e.v("to")),
                        ),
                    ),
                ),
            ),
            e.ret(make(e.v("valuecv"), e.v("to"))),
        ),
    )


def alloc_or_trap(e, alloc, to_int, int_ty, trap):
    """`alloc` (a pointer expression) when it is not null, else `trap` (a statement): `to_int` is the target's
    `ptr_to_int` and `int_ty` its address-sized integer type, both resolved for the staging depth. Allocation failure
    is never a value to handle: nothing in the language can recover from it."""
    return e.mb.labeled(
        "alloc",
        e.seq(
            e.let("__p", alloc),
            e.if_only(e.eq(conv(e, to_int, e.v("__p"), int_ty), e.n(0)), trap),
            e.mb.return_to("alloc", e.v("__p")),
        ),
    )


def conv(e, fn, value, to):
    """A call of a named conversion `fn` (`ptr_cast`, `ptr_to_int`, `int_to_ptr`, `fn_to_ptr`, resolved for the
    caller's staging depth) of `value` to the type `to`."""
    return e.call(fn, e.rec(p("value", value), p("to", to)))


def dep_type(e, x, obj, desc, fields, h_fn, with_argument, binding_obj):
    """A dependency as a callable type: its function value (the unit cast to it) calls the host function `h_fn` with
    the stored `fields` (name first) after its identity `id` (a fresh unique the constructor mints: two dependencies
    are the same only when they are the same instance, never because their names agree), and the call's argument
    when `with_argument`."""
    fields = [("id", unique_t(e))] + list(fields)
    def_iface(e, x, obj + "_m", p("id", unique_t(e)))
    def_obj(e, x, obj, desc, e.rec(*[p(f, ft) for f, ft in fields]))
    x.append(e.impl_interface(e.v(obj), t(e, obj + "_m"), p("id", in_(e, "id"))))
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
                    e.eq(in_(e, "id"), acc(e, xx(e), a(e, "other"), obj + "_m", "id")),
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
    # Its function value lifts as itself: the empty value of the (same) dependency type, still callable.
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_lift(),
            p("lift", e.eresult_ok(e.mb.eval_value(), e.call(e.eval_builtin("value_empty"), outer(e)))),
        )
    )


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
    """Binds `bind` to the type the code-value `cv` holds, else errors out of the const function: a constant type
    (its type has the `type` aspect), or a type value computed at compile time (typed `eval.type`, as a type made in
    a const function's staged result is), never target code."""
    return [
        e.let(bind + "_tk", lookup(e, xx(e), cve_type(e, cv), asp_iface(e, "type"))),
        e.let(bind + "_dyn", is_equal(e, xx(e), cve_type(e, cv), e.mb.eval_type())),
        e.if_only(
            is_runtime(e, cv),
            ret_m(e, err_cve(e, loc(e), label + ": " + bind + " must be a type known at compile time, not target code")),
        ),
        e.if_only(
            e.not_(or_b(e, e.fld(e.v(bind + "_tk"), "is_some"), e.v(bind + "_dyn"))),
            ret_m(
                e,
                err_cve(
                    e,
                    loc(e),
                    e.cat(e.s(label + ": " + bind + " must be a type, not a "), ty_desc(e, cve_type(e, cv))),
                ),
            ),
        ),
        e.let(
            bind,
            e.if_else(
                e.v(bind + "_dyn"),
                e.call(e.mb.must_reinterpret(), e.tup(cve_value(e, cv), e.mb.eval_type())),
                bim(e, asp_iface(e, "type"), "type", e.fld(e.v(bind + "_tk"), "value"), cve_value(e, cv)),
            ),
        ),
    ]


def method_fields(e, x, obj, meth_obj, methods, when=None):
    """`field` on `obj` values: each name in `methods` yields a bound method, a value of the callable type `meth_obj`
    (field `op`, the name) whose data is the receiver and whose call runs the operation; `when(name)`, when given,
    is a condition (over the type's fields) for the method to exist."""

    def cond(m):
        same = e.eq(e.v("key"), e.s(m))
        return same if when is None else and_b(e, same, when(m))

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
                            cond(m),
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
                                                    mk(e, meth_obj, p("op", e.s(m))),
                                                ),
                                                p(
                                                    "data",
                                                    as_object(
                                                        e, cv_of(e, code_none(e, loc(e)), cve_value(e, a(e, "self")))
                                                    ),
                                                ),
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
    """A bound method's type: `{op}`, callable (its `function` aspect is implemented by the caller); a value's data
    is the receiver."""
    def_obj(e, x, obj, desc, e.rec(p("op", str_(e))))
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


def staged_in(e, expr):
    return unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(expr)))


def codes(e, *codes):
    return unwrap_m(e, code_seq(e, *codes), e.mb.types_cve())


def retag_values(e, cv, typ):
    """The runtime value of `cv` (a variable reference) viewed as `typ` (values.atz), with the code of `cv`."""
    retag = e.lower(e.fld(e.v("values"), "retag"))
    return cv_of(
        e,
        cve_code(e, cv),
        bim(e, retag, "retag", e.call(e.mb.must_reinterpret(), e.tup(cve_value(e, cv), retag)), typ),
    )


def self_v(e, type_field="pv"):
    """The handle value (the receiver `recv`) in a method body's staged code, as one of the handle's types."""
    return e.mb.as_(graft(e, e.v("recv")), e.lower(e.v(type_field)))


def handle_binding(e, x, obj, desc):
    """A binding of a handle value: the representation's binding (`inner`), whose uses are retagged as the handle
    type (`ty`); assignments through it rebind the representation and wrap again."""
    bt = e.mb.eval_binding()
    st = e.mb.builtin("eval", "binding_setter")
    setter_obj = obj + "_s"
    def_obj(e, x, obj, desc, e.rec(p("inner", bt), p("ty", ty(e))))
    accessor(e, x, obj, "inner", bt)
    def_obj(e, x, setter_obj, desc + " setter", e.rec(p("setter", st), p("ty", ty(e))))

    def wrap(inner):
        return mk(e, obj, p("inner", inner), p("ty", in_(e, "ty")))

    x.append(
        e.impl_interface(
            e.v(obj),
            bt,
            p(
                "use",
                retag_values(
                    e,
                    bim(
                        e,
                        bt,
                        "use",
                        in_(e, "inner"),
                        e.rec(
                            p("xx", xx(e)),
                            p("loc", loc(e)),
                            p("setter", mk(e, setter_obj, p("setter", a(e, "setter")), p("ty", in_(e, "ty")))),
                            p("code", a(e, "code")),
                        ),
                    ),
                    in_(e, "ty"),
                ),
            ),
            p("drop", bim(e, bt, "drop", in_(e, "inner"), e.rec(p("xx", xx(e)), p("loc", loc(e))))),
            p("fork", wrap(bim0(e, bt, "fork", in_(e, "inner")))),
            p(
                "merge",
                body(
                    e,
                    e.let("inners", e.list_new(bt)),
                    e.foreach(
                        a(e, "others"),
                        "o",
                        e.push(e.v("inners"), e.call_m(reinterpret(e, e.v("o"), obj), "inner", e.tup())),
                    ),
                    e.let(
                        "m",
                        unwrap_m(
                            e,
                            bim(
                                e,
                                bt,
                                "merge",
                                in_(e, "inner"),
                                e.rec(p("xx", xx(e)), p("loc", loc(e)), p("others", e.v("inners"))),
                            ),
                            bt,
                        ),
                    ),
                    e.ret(e.eresult_ok(bt, wrap(e.v("m")))),
                ),
            ),
        )
    )
    x.append(
        e.impl_interface(
            e.v(setter_obj),
            st,
            p(
                "set",
                bim(
                    e,
                    st,
                    "set",
                    in_(e, "setter"),
                    e.rec(
                        p("xx", xx(e)),
                        p("loc", loc(e)),
                        p("new_binding", mk(e, obj, p("inner", a(e, "new_binding")), p("ty", in_(e, "ty")))),
                        p("drop_modified", a(e, "drop_modified")),
                    ),
                ),
            ),
        )
    )


def handle_binds(e, x, obj, under, binding_obj, desc):
    """`bind` and `initial_bind` of a handle type: the representation's, wrapped so uses keep the handle type."""
    br_t = e.mb.types_bind_result()
    bt = e.mb.eval_binding()

    def wrap(inner):
        return mk(e, binding_obj, p("inner", inner), p("ty", outer(e)))

    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_bind(),
            p(
                "bind",
                body(
                    e,
                    e.let("ub", lookup(e, xx(e), in_(e, under), e.mb.eval_aspect_bind())),
                    e.if_only(
                        e.not_(e.fld(e.v("ub"), "is_some")),
                        ret_m(e, e.eresult_err(br_t, loc(e), e.s(desc + ": the representation cannot be bound"))),
                    ),
                    e.let(
                        "r",
                        unwrap_m(
                            e,
                            bim(
                                e,
                                e.mb.eval_aspect_bind(),
                                "bind",
                                e.fld(e.v("ub"), "value"),
                                e.rec(
                                    p("xx", xx(e)),
                                    p("loc", loc(e)),
                                    p("cv", retag_values(e, a(e, "cv"), in_(e, under))),
                                ),
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
                                    p("code", e.fld(e.v("r"), "code")), p("binding", wrap(e.fld(e.v("r"), "binding")))
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    )
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_initial_bind(),
            p(
                "initial_bind",
                body(
                    e,
                    e.let("ui", lookup(e, xx(e), in_(e, under), e.mb.eval_aspect_initial_bind())),
                    e.if_only(
                        e.not_(e.fld(e.v("ui"), "is_some")),
                        ret_m(e, e.eresult_err(bt, loc(e), e.s(desc + ": the representation cannot be a parameter"))),
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
                                e.rec(p("xx", xx(e)), p("loc", loc(e)), p("slot", a(e, "slot"))),
                            ),
                            bt,
                        ),
                    ),
                    e.ret(e.eresult_ok(bt, wrap(e.v("r")))),
                ),
            ),
        )
    )


def handle_type(
    e,
    x,
    obj,
    iface,
    desc,
    fields,
    places,
    methods,
    under="pv",
    from_under=True,
    desc_expr=None,
    identity=None,
    ptr_cast=None,
):
    """A handle type over a representation (the field `under`: a pointer, or a tuple): its field aspect gives the
    places (`places` maps a name to the staged place over `self_as`, the handle as its representation or, through
    `ptr_cast`, a host expression for the target's pointer conversion bound as the host local `ptr_cast`, as one of
    its other pointer-typed fields) and the methods;
    it delegates the rest to the representation and retags from its values. With `from_under`, a value of exactly
    the representation type casts to the handle (a pointer handle is made from its pointer); without, only the handle
    itself does, and the module offers a constructor. `desc_expr` is the type's description when it is not the
    constant `desc`; `identity` names the field that two handle types must agree on to be equal (the element or key
    type), else any two are."""
    def_iface(e, x, iface, *fields)
    def_obj(e, x, obj, desc, e.rec(*fields))
    x.append(e.impl_interface(e.v(obj), t(e, iface), *[p(k, in_(e, k)) for k, _ in fields]))
    self_type(
        e,
        x,
        obj,
        desc_expr if desc_expr is not None else e.s(desc),
        e.mb.if_of(
            [
                (e.eq(a(e, "key"), asp_id(e, "field")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), asp_id(e, "bind")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), asp_id(e, "initial_bind")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), lv(e, iface + "_id")), e.opt_some(e.mb.types_aspect(), outer(e))),
            ],
            type_aspect(e, xx(e), in_(e, under), a(e, "key")),
        ),
        body(
            e,
            e.ret(
                (
                    or_b(
                        e,
                        is_equal(e, xx(e), outer(e), a(e, "source_type")),
                        is_equal(e, xx(e), in_(e, under), a(e, "source_type")),
                    )
                    if from_under
                    else is_equal(e, xx(e), outer(e), a(e, "source_type"))
                )
            ),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), cve_type(e, a(e, "cv"))), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.let("uv", a(e, "cv")),
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
        # A handle casts to its representation.
        body(e, e.ret(is_equal(e, xx(e), in_(e, under), a(e, "dest_type")))),
        body(e, e.ret(ok_cve(e, retag_values(e, a(e, "cv"), in_(e, under))))),
        body(
            e,
            e.ret(
                has(e, xx(e), a(e, "other"), iface)
                if identity is None
                else and_b(
                    e,
                    has(e, xx(e), a(e, "other"), iface),
                    is_equal(e, xx(e), in_(e, identity), acc(e, xx(e), a(e, "other"), iface, identity)),
                )
            ),
        ),
    )
    handle_binding(e, x, obj + "_b", desc + " binding")
    handle_binds(e, x, obj, under, obj + "_b", desc)
    meth = obj + "_meth"
    def_obj(e, x, meth, desc + " method", e.rec(p("kind", str_(e)), p("ht", ty(e))))

    def self_as(type_field):
        as_under = e.mb.as_(graft(e, a(e, "self")), e.lower(in_(e, under)))
        if type_field == under:
            return as_under
        if ptr_cast is None:
            raise ValueError(obj + ": places over " + type_field + " need the handle type's ptr_cast")
        return conv(e, e.lower(e.v("ptr_cast")), as_under, e.lower(in_(e, type_field)))

    x.append(
        e.impl_interface(
            e.v(obj),
            asp_iface(e, "field"),
            p(
                "field",
                body(
                    e,
                    e.if_only(
                        e.not_(has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
                        ret_m(e, err_cve(e, loc(e), desc + ": field must be a constant string")),
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
                    *([] if ptr_cast is None else [e.let("ptr_cast", ptr_cast)]),
                    *[
                        e.if_only(e.eq(e.v("key"), e.s(name)), ret_m(e, ok_cve(e, staged_in(e, place(self_as)))))
                        for name, place in places.items()
                    ],
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
                                                    mk(e, meth, p("kind", e.s(m)), p("ht", outer(e))),
                                                ),
                                                p(
                                                    "data",
                                                    as_object(
                                                        e, cv_of(e, code_none(e, loc(e)), cve_value(e, a(e, "self")))
                                                    ),
                                                ),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        )
                        for m in methods
                    ],
                    e.ret(err_cve(e, loc(e), e.cat(e.s(desc + " has no field "), e.v("key")))),
                ),
            ),
            p("type_opt", e.option_type_lowered_none()),
            p(
                "keys",
                e.list_new(
                    e.mb.types_constkey(),
                    *[e.mb.as_(e.s(k), e.mb.types_constkey()) for k in list(places) + methods],
                ),
            ),
        )
    )
    no = e.mb.as_(e.b(False), bool_t(e))
    self_type(
        e,
        x,
        meth,
        e.cat(e.s(desc + "."), in_(e, "kind")),
        e.aspect_dispatch(asp_id(e, "function")),
        no,
        cast_to_panic(e),
        no,
        cast_to_panic(e),
        no,
    )
    return meth


def handle_methods(e, x, meth, iface, fields, methods, method_body, prelude=(), host=(), kind_prelude=None):
    """The call of a handle method: `method_body(kind)` is the staged operation over the handle's fields (host
    locals of the field names) and `self_v`, the handle value, or for the kinds in `host` a host expression yielding
    the staged code value itself; `prelude` are host statements run first, `kind_prelude` maps a kind to host
    statements run before its operation."""

    def dispatch(kind):
        result = method_body(kind) if kind in host else staged_in(e, method_body(kind))
        before = (kind_prelude or {}).get(kind, ())
        return e.if_only(e.eq(in_(e, "kind"), e.s(kind)), e.seq(*before, *call_result(e, result)))

    x.append(
        e.impl_interface(
            e.v(meth),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    e.let("recv", recv_of(e)),
                    *[e.let(f, acc(e, xx(e), in_(e, "ht"), iface, f)) for f, _ in fields],
                    *prelude,
                    *[dispatch(kind) for kind in methods],
                    e.ret(err_cve(e, loc(e), e.cat(e.s("json: unknown method "), in_(e, "kind")))),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )
