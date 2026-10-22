"""js-es2020.atz: JavaScript target, typed: every value has one js type, and everything the generated code uses from
its runtime (globals, functions, constructors, object members) is declared with a type. No runtime checks.

Types: `number` and `bigint` (js's two numeric primitives, with js's operators: `/` divides as floats, the bitwise
operators work as js defines them, `>>>` is number-only), `bool`, `string` (`+`, comparisons, `length`), `null` and
`undefined` (their value is `() as js.null`), `void` (a function's absent result); the const functions `fn{params:
(T, ...), ret}`, `ctor{params, ret}` (a call is `new`), `array{elem}` (`length`, `a[i]`, `push`, `foreach`; a tuple
converts to an array literal), `object{name}` (a nominal object type, identified by its name; `members{object,
fields, methods}` declares its members, so declarations can refer to each other; a record with exactly its fields
converts to an object literal; a method value keeps its receiver as `this`), `union{k: T, ...}` (an untagged union
whose members have distinct runtime tags; `match` tests `typeof`/`=== null`/...). `global_fn{name, ty}`, `var_fn{mod,
name, ty}` and `func_fn{mod, name, params, ty, body}` define and declare values. `as` converts losslessly
(constants, members into unions); `n.to_bigint(())` and `b.to_number(())` convert between the numbers.

Every call and `new` lands in a fresh `var`; a binding of such a value is that variable itself (no copy), while a
binding of any other expression copies it into a fresh `var`; operators, fields and literals are pure expressions.
Bindings are never reassigned. Names: functions and temporaries are minted per module (`hint$n`); `declare`d
variables keep their names for the module's text helpers (`func_text`, `assign_index`), which stay untyped text.

A `return` to a block exits with `break`: the block's landing is a marker statement, and when a region's statements
(a function body, an `if`/`match` arm or condition, a loop body) are laid out, everything from the region's start to
the marker is wrapped in a labeled block, `$Ln: { ... }`, as the wat target opens its `block`s. The wrap can take in
variables the code after the block uses, so they are `var`s (function scoped) rather than block scoped `const`s.
A returned runtime value goes into a slot variable whose type names it (`jt_slot`); later returns to the block convert
into the first one's slot. Exceptions are not supported: the language's `throw` is the dynamic target's."""

from .. import target_mb
from ..core import srcmap, values
from .. import target_mb as tm
from ..target_mb import (
    ty_desc,
    recv_of,
    op_id,
    op_iface,
    as_object,
    a,
    acc,
    accessor,
    and_b,
    asp_id,
    asp_iface,
    bim,
    bim0,
    binding_drop_body,
    body,
    bool_t,
    can_cast_from_self,
    cast_from_self,
    cast_to_panic,
    cast_value,
    code_none,
    code_t,
    const_eval_in,
    count_let,
    count_loop,
    cv_no,
    cv_of,
    cve_code,
    cve_ended,
    cve_has,
    cve_t,
    cve_type,
    cve_value,
    def_iface,
    def_obj,
    dfalse,
    err_cve,
    fn_impl,
    graft,
    has,
    has_b,
    hf,
    hf_rec,
    in_,
    int_t,
    is_const,
    is_equal,
    is_runtime,
    is_target_code,
    key_str,
    loc,
    loc_t,
    lookup,
    lookup_v,
    lt,
    lv,
    marker_type,
    method,
    mk,
    mk_arg,
    must_v,
    no_cast_to,
    num,
    ok_cve,
    or_b,
    outer,
    panic_errs,
    push,
    reinterpret,
    ret_m,
    rt_bind_impl,
    rt_dispatch,
    rt_lift_impl,
    rt_use_impl,
    self_type,
    src_type,
    str_,
    structural_exits,
    t,
    tag_value,
    target_drop_body,
    to_str,
    ty,
    type_aspect,
    type_can_cast_from,
    unwrap_cve_m,
    unwrap_m,
    voc_t,
    xx,
    xx_t,
)

TARGET = "js"

JGFN_KINDS = ["global_fn", "func_fn", "var_fn", "fn", "ctor", "array", "object", "members", "union"]


def _fn_def(e, out, name, arg_type, ret):
    return target_mb.fn_def(e, out, TARGET, name, arg_type, ret)


VLQ_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def _jmod_t(e):
    return t(e, "jmod")


def _render_t(e):
    return e.rec(e.p("js", str_(e)), e.p("map", str_(e)), e.p("frames", str_(e)))


def _insts_t(e):
    return e.list_type(t(e, "jinst"))


def _insts_new(e):
    return e.list_new(lt(e, "jinst"))


def _inst(e, text, loc_):
    return mk(e, "jinst", e.p("text", text), e.p("loc", loc_), e.p("label", e.opt_none(str_(e))))


def _label_inst(e, name, loc_):
    """The landing of the labeled block `name`: its closing `}`, whose opening is placed when its region is laid out
    (`h_resolve`)."""
    return mk(e, "jinst", e.p("text", e.dstr("}")), e.p("loc", loc_), e.p("label", e.opt_some(str_(e), name)))


def _cell(e, name, value):
    return e.let(name, e.rec(e.p("v", value)))


def _cv(e, name):
    return e.fld(e.v(name), "v")


def _unit_t(e, obj):
    return mk_arg(e, obj, e.tup())


def _bool_t(e):
    return _unit_t(e, "jt_bool")


def _string_t(e):
    return _unit_t(e, "jt_string")


def _jval(e, ty_, expr, temp=False, place=False):
    """A js value: its type and the expression reading it. `temp`: the expression is a fresh `var` of its own (a
    binding reuses it); `place`: the expression can be assigned to (a variable, field or element)."""
    temp_ = e.b(temp) if isinstance(temp, bool) else temp
    place_ = e.b(place) if isinstance(place, bool) else place
    return mk(e, "jval", e.p("ty", ty_), e.p("expr", expr), e.p("temp", temp_), e.p("place", place_))


def _jv(e, cve_tp):
    return reinterpret(e, cve_value(e, cve_tp), "jval")


def _jv_expr(e, cve_tp):
    return e.call_m(_jv(e, cve_tp), "expr", e.tup())


def _append_code(e, out, code_tp):
    return hf_rec(e, "h_append", e.p("out", out), e.p("code", code_tp))


def _code_of(e, insts):
    return hf(e, "h_code", insts)


def _fresh(e, mod):
    return e.call_m(mod, "fresh", e.tup())


def _xmod(e):
    return _xmod_ret(e, e.mb.types_cve())


def _xmod_ret(e, ret_inner):
    return e.call_m(
        unwrap_m(e, e.call(e.mb.reinterpret(), e.tup(loc(e), e.fld(xx(e), "target"), lt(e, "jtarget"))), ret_inner),
        "mod",
        e.tup(),
    )


def _to(e, ty_, cv):
    """`cv` converted to the js type `ty_` (the type's own casts: literals, lossless widenings, loads); in a body
    returning `eresult(cve)`, a failed conversion returns its errors."""
    return unwrap_cve_m(e, cast_value(e, xx(e), loc(e), ty_, cv))


def _is_js(e, xx_, cv):
    return hf_rec(e, "h_is_js", e.p("xx", xx_), e.p("cv", cv))


def _tag(e, xx_, typ):
    """The js runtime tag of a js type (`typeof`'s answer, or `null`/`undefined`): what a union tells members by."""
    return acc(e, xx_, typ, "jtype_m", "tag")


def _arm_stmts(e, cv_var):
    """Appends an arm's statements to `bo`, assigning its value (if any) to the result variable, converted to the
    first valued arm's type (`rt`), and tracks in `st` whether arms have values and whether any falls through."""
    valued = cve_has(e, e.v(cv_var))
    return e.seq(
        e.if_only(e.not_(valued), _append_code(e, e.v("bo"), cve_code(e, e.v(cv_var)))),
        e.if_only(
            valued,
            e.seq(
                e.mb.set(e.fld(e.v("st"), "has"), num(e, 1)),
                e.if_only(
                    e.eq(e.fld(e.v("st"), "typed"), num(e, 0)),
                    e.seq(
                        e.if_only(
                            e.not_(_is_js(e, xx(e), e.v(cv_var))),
                            ret_m(e, err_cve(e, loc(e), "the first valued branch must yield a js value")),
                        ),
                        push(e, e.v("rt"), cve_type(e, e.v(cv_var))),
                        e.mb.set(e.fld(e.v("st"), "typed"), num(e, 1)),
                    ),
                ),
                e.let("bv", _to(e, e.call_m(e.v("rt"), "get", e.int_of(0)), e.v(cv_var))),
                _append_code(e, e.v("bo"), cve_code(e, e.v("bv"))),
                push(
                    e,
                    e.v("bo"),
                    _inst(e, e.cat(e.fld(e.v("st"), "res"), e.s(" = "), _jv_expr(e, e.v("bv")), e.s(";")), loc(e)),
                ),
            ),
        ),
        e.if_only(
            and_b(e, e.not_(valued), e.not_(cve_ended(e, e.v(cv_var)))),
            e.mb.set(e.fld(e.v("st"), "novalue"), num(e, 1)),
        ),
        e.if_only(e.not_(cve_ended(e, e.v(cv_var))), e.mb.set(e.fld(e.v("st"), "ended"), num(e, 0))),
    )


def _indent(e, depth):
    """Two spaces per nesting level up to `depth` (bounded by the arm count)."""
    return e.seq(
        e.let("__pre", e.rec(e.p("v", e.dstr("")))),
        e.let("__k", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(
            e.v("arms"),
            "_",
            e.seq(
                e.if_only(
                    e.mb.operator_lt(e.fld(e.v("__k"), "v"), depth),
                    e.mb.set(e.fld(e.v("__pre"), "v"), e.cat(e.fld(e.v("__pre"), "v"), e.s("  "))),
                ),
                e.incr(e.fld(e.v("__k"), "v")),
            ),
        ),
        e.ret(e.fld(e.v("__pre"), "v")),
    )


def _push_indented(e, insts, pre, extra):
    """Lays out a region's statements (`h_resolve`) and appends them to `out` indented."""
    return e.foreach(
        hf(e, "h_resolve", insts),
        "i0",
        push(
            e,
            e.v("out"),
            _inst(e, e.cat(pre, e.s(extra), e.call_m(e.v("i0"), "text", e.tup())), e.call_m(e.v("i0"), "loc", e.tup())),
        ),
    )


def _arms_t(e):
    return e.list_type(e.rec(e.p("condition", cve_t(e)), e.p("body", cve_t(e))))


def _arms_layout(e, *pre):
    """A structured `if`/`match` over `arms` (a list of `{condition, body}`, each condition a `bool`) and `els` (the
    optional else body), after the statements `pre` (which also append to `out`, e.g. a match's base code): each later
    condition nests in the previous `else` (its statements run only there); a valued result is a variable assigned in
    every arm, typed by the first valued arm."""
    return body(
        e,
        e.let("mod", _xmod(e)),
        e.let("out", _insts_new(e)),
        *pre,
        e.let(
            "st",
            e.rec(
                e.p("ended", e.int_of(1)),
                e.p("has", e.int_of(0)),
                e.p("novalue", e.int_of(0)),
                e.p("typed", e.int_of(0)),
                e.p("res", _fresh(e, e.v("mod"))),
            ),
        ),
        e.let("rt", e.list_new(ty(e))),
        count_let(e, "nc"),
        count_loop(e, "nc", e.v("arms")),
        e.let("ci", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(
            e.v("arms"),
            "br",
            e.seq(
                e.let("c", _to(e, _bool_t(e), e.fld(e.v("br"), "condition"))),
                e.let("pre", _indent(e, e.fld(e.v("ci"), "v"))),
                e.let("cl", _insts_new(e)),
                _append_code(e, e.v("cl"), cve_code(e, e.v("c"))),
                _push_indented(e, e.v("cl"), e.v("pre"), ""),
                push(
                    e, e.v("out"), _inst(e, e.cat(e.v("pre"), e.s("if ("), _jv_expr(e, e.v("c")), e.s(") {")), loc(e))
                ),
                e.let("bo", _insts_new(e)),
                e.let("b", e.fld(e.v("br"), "body")),
                _arm_stmts(e, "b"),
                _push_indented(e, e.v("bo"), e.v("pre"), "  "),
                e.incr(e.fld(e.v("ci"), "v")),
                e.if_else(
                    or_b(
                        e,
                        e.mb.operator_lt(e.fld(e.v("ci"), "v"), e.fld(e.v("nc"), "v")),
                        e.fld(e.v("els"), "is_some"),
                    ),
                    push(e, e.v("out"), _inst(e, e.cat(e.v("pre"), e.s("} else {")), loc(e))),
                    push(e, e.v("out"), _inst(e, e.cat(e.v("pre"), e.s("}")), loc(e))),
                ),
            ),
        ),
        e.if_only(
            e.fld(e.v("els"), "is_some"),
            e.seq(
                e.let("pre", _indent(e, e.fld(e.v("nc"), "v"))),
                e.let("bo", _insts_new(e)),
                e.let("b", e.fld(e.v("els"), "value")),
                _arm_stmts(e, "b"),
                _push_indented(e, e.v("bo"), e.v("pre"), ""),
                # With no arms (a one-case match), the else body stands alone.
                e.if_only(
                    e.mb.operator_gt(e.fld(e.v("nc"), "v"), num(e, 0)),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e, e.cat(_indent(e, e.mb.operator_sub(e.fld(e.v("nc"), "v"), num(e, 1))), e.s("}")), loc(e)
                        ),
                    ),
                ),
            ),
        ),
        e.if_only(
            e.not_(e.fld(e.v("els"), "is_some")),
            e.seq(
                e.mb.set(e.fld(e.v("st"), "ended"), num(e, 0)),
                e.if_only(e.eq(e.fld(e.v("st"), "has"), num(e, 1)), e.mb.set(e.fld(e.v("st"), "novalue"), num(e, 1))),
            ),
        ),
        e.let("depth", e.rec(e.p("v", e.mb.operator_sub(e.fld(e.v("nc"), "v"), num(e, 2))))),
        e.foreach(
            e.v("arms"),
            "_",
            e.if_only(
                e.mb.operator_ge(e.fld(e.v("depth"), "v"), num(e, 0)),
                e.seq(
                    push(e, e.v("out"), _inst(e, e.cat(_indent(e, e.fld(e.v("depth"), "v")), e.s("}")), loc(e))),
                    e.mb.set(e.fld(e.v("depth"), "v"), e.mb.operator_sub(e.fld(e.v("depth"), "v"), num(e, 1))),
                ),
            ),
        ),
        e.if_only(
            e.eq(e.fld(e.v("st"), "ended"), num(e, 1)),
            ret_m(e, ok_cve(e, e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("out"))))),
        ),
        e.if_only(e.eq(e.fld(e.v("st"), "has"), num(e, 0)), ret_m(e, ok_cve(e, cv_no(e, _code_of(e, e.v("out")))))),
        e.if_only(
            e.eq(e.fld(e.v("st"), "novalue"), num(e, 1)),
            ret_m(e, err_cve(e, loc(e), "some branches yield a value and some do not")),
        ),
        e.let("all", _insts_new(e)),
        push(e, e.v("all"), _inst(e, e.cat(e.s("var "), e.fld(e.v("st"), "res"), e.s(";")), loc(e))),
        e.foreach(e.v("out"), "i0", push(e, e.v("all"), e.v("i0"))),
        e.ret(
            ok_cve(
                e,
                cv_of(
                    e,
                    _code_of(e, e.v("all")),
                    _jval(e, e.call_m(e.v("rt"), "get", e.int_of(0)), e.fld(e.v("st"), "res")),
                ),
            )
        ),
    )


def _if_hook(e):
    """A structured `if` (`_arms_layout`) over the target's conditions."""
    return _arms_layout(
        e,
        e.let("arms", e.list_new(e.rec(e.p("condition", cve_t(e)), e.p("body", cve_t(e))))),
        e.foreach(
            a(e, "conditions"),
            "cb",
            push(
                e,
                e.v("arms"),
                e.rec(e.p("condition", e.fld(e.v("cb"), "condition")), e.p("body", e.fld(e.v("cb"), "body"))),
            ),
        ),
        e.let("els", a(e, "else")),
    )


def _const_str(e, cv):
    return hf_rec(e, "h_const_str", e.p("xx", xx(e)), e.p("cv", cv))


def _param_t(e):
    return e.rec(e.p("name", str_(e)), e.p("ty", ty(e)))


def _params_t(e):
    return e.list_type(_param_t(e))


def _args_t(e):
    return e.rec(e.p("code", code_t(e)), e.p("exprs", e.list_type(str_(e))))


def _args_of(e, params):
    """The call's arguments converted to the parameter types `params` (the argument itself for one parameter,
    otherwise a tuple of one element per parameter)."""
    return unwrap_m(
        e,
        hf_rec(e, "h_args", e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("cv", a(e, "argument")), e.p("params", params)),
        cve_t(e),
    )


def _jgfn_kind(kind):
    return JGFN_KINDS.index(kind)


def _jgfn_is(e, kind):
    return e.eq(in_(e, "kind"), num(e, _jgfn_kind(kind)))


def _jgfn_staged(e, staged):
    return unwrap_cve_m(e, const_eval_in(e, xx(e), loc(e), e.stage(staged)))


def _jgfn_field(e, key):
    """The definition argument's field `key` (a name, or an expression)."""
    key_ = e.s(key) if isinstance(key, str) else key
    return unwrap_cve_m(e, e.call_m(e.v("fields"), "get", key_))


def _push_utf8(e, out, text):
    return e.foreach(e.call(e.mb.eval_str_utf8(), text), "__b", push(e, out, e.v("__b")))


def _lines(e, insts, out, frames_out, indent):
    """Lays out a function's or the module's statements (`h_resolve`), appending their text to `out` (a jmod's line
    list) and each one's frame to `frames_out`."""
    return e.foreach(
        hf(e, "h_resolve", insts),
        "i0",
        e.seq(
            push(e, out, e.cat(e.s(indent), e.call_m(e.v("i0"), "text", e.tup()))),
            push(e, frames_out, _frame(e, e.call_m(e.v("i0"), "loc", e.tup()))),
        ),
    )


def _frame(e, loc_):
    return e.call_m(in_(e, "frames"), "index", loc_)


def _no_frame(e):
    return e.int_of(-1)



# Each js type's own identity marker: a type that stands in for another (a slot, a global) answers every aspect of
# the type it holds except these, so it never passes for that type.
JT_IDENT = [
    "jnumber_m",
    "jbigint_m",
    "jbool_m",
    "jstring_m",
    "jnull_m",
    "jundef_m",
    "jvoid_m",
    "jfn_m",
    "jctor_m",
    "jslot_m",
    "jglobal_m",
    "jarray_m",
    "jmethod_m",
    "jobj_m",
    "junion_m",
]

CMP_OPS = {"eq": "===", "ne": "!==", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}
NUM_BIN = {
    "add": "+",
    "sub": "-",
    "mul": "*",
    "div": "/",
    "mod": "%",
    "and": "&",
    "or": "|",
    "xor": "^",
    "shl": "<<",
    "shr": ">>",
    "ushr": ">>>",
}


def _cat(e, *parts):
    return e.cat(*[e.s(p_) if isinstance(p_, str) else p_ for p_ in parts])


def _op_impl(e, x, obj, op_, rty, expr_of, unary=False):
    """`op_` on `obj` values: both operands converted to this type (`outer`), the result a pure expression of type
    `rty`; `expr_of(a, b)` gives the expression (an expr) from the operands' expressions."""
    stmts = [e.let("o1", _to(e, outer(e), a(e, "base")))]
    if not unary:
        stmts.append(e.let("o2", _to(e, outer(e), a(e, "reference"))))
    stmts.append(e.let("out", _insts_new(e)))
    stmts.append(_append_code(e, e.v("out"), cve_code(e, e.v("o1"))))
    if not unary:
        stmts.append(_append_code(e, e.v("out"), cve_code(e, e.v("o2"))))
    a_ = _jv_expr(e, e.v("o1"))
    b_ = None if unary else _jv_expr(e, e.v("o2"))
    stmts.append(e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _jval(e, rty, expr_of(a_, b_))))))
    x.append(e.impl_interface(e.v(obj), op_iface(e, op_), e.p(op_, body(e, *stmts))))


def _bind_impl(e, x, obj):
    """`let` of an `obj` value: a value already in a fresh `var` of its own is the binding; anything else is copied
    into one."""
    br_t = e.mb.types_bind_result()
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_bind(),
            e.p(
                "bind",
                body(
                    e,
                    e.let("v", unwrap_m(e, cast_value(e, xx(e), loc(e), outer(e), a(e, "cv")), br_t)),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                    e.let("jv", _jv(e, e.v("v"))),
                    e.let("temp", e.call_m(e.v("jv"), "temp", e.tup())),
                    e.let(
                        "r",
                        e.if_else(e.v("temp"), e.call_m(e.v("jv"), "expr", e.tup()), _fresh(e, _xmod_ret(e, br_t))),
                    ),
                    e.if_only(
                        e.not_(e.v("temp")),
                        push(
                            e,
                            e.v("out"),
                            _inst(
                                e, _cat(e, "var ", e.v("r"), " = ", e.call_m(e.v("jv"), "expr", e.tup()), ";"), loc(e)
                            ),
                        ),
                    ),
                    e.ret(
                        e.eresult_ok(
                            br_t,
                            e.call(
                                e.mb.eval_bind_result(),
                                e.rec(
                                    e.p("code", _code_of(e, e.v("out"))),
                                    e.p("binding", mk(e, "jbinding", e.p("name", e.v("r")), e.p("ty", outer(e)))),
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    )


def _set_impl(e, x, obj):
    """Assignment to an `obj` place (a variable, field or element): `target = value;`, the value converted to the
    place's type."""
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_set(),
            e.p(
                "set",
                body(
                    e,
                    e.let("t", _to(e, outer(e), a(e, "target"))),
                    e.if_only(
                        e.not_(e.call_m(_jv(e, e.v("t")), "place", e.tup())),
                        ret_m(e, err_cve(e, loc(e), "js: this value is not a variable, field or element")),
                    ),
                    e.let("v", _to(e, outer(e), a(e, "value"))),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("t"))),
                    _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                    push(
                        e,
                        e.v("out"),
                        _inst(e, _cat(e, _jv_expr(e, e.v("t")), " = ", _jv_expr(e, e.v("v")), ";"), loc(e)),
                    ),
                    e.ret(ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                ),
            ),
        )
    )


def _js_type(
    e, x, obj, desc, marker, aspect_ids, can_cast_from, cast_from, is_equal_, tag, marker_fields=(), exporter=None
):
    """A js value type: `desc`, its own identity `marker` (implemented with `marker_fields`, pairs of a marker method
    and its value), `jtype_m` (its runtime tag), `bind` and `set`, plus `aspect_ids` (implemented by the caller)."""
    self_type(
        e,
        x,
        obj,
        desc,
        e.aspect_dispatch(lv(e, "jtype_m_id"), lv(e, marker + "_id"), asp_id(e, "bind"), asp_id(e, "set"), *aspect_ids),
        can_cast_from,
        cast_from,
        no_cast_to(e),
        cast_to_panic(e),
        is_equal_,
        exporter,
    )
    x.append(e.impl_interface(e.v(obj), t(e, marker), *[e.p(k, v) for k, v in marker_fields]))
    x.append(e.impl_interface(e.v(obj), t(e, "jtype_m"), e.p("tag", tag), e.p("base", outer(e))))
    _bind_impl(e, x, obj)
    _set_impl(e, x, obj)


def _stand_in_dispatch(e, own_marker, held):
    """The aspects of a type standing in for the type `held` (a slot, a global): its own marker, none of the js
    types' identity markers, and every other aspect of `held`."""
    ident = e.eq(a(e, "key"), lv(e, JT_IDENT[0] + "_id"))
    for m in JT_IDENT[1:]:
        ident = or_b(e, ident, e.eq(a(e, "key"), lv(e, m + "_id")))
    return e.mb.if_of(
        [
            (e.eq(a(e, "key"), lv(e, own_marker + "_id")), e.opt_some(e.mb.types_aspect(), outer(e))),
            (ident, e.opt_none(e.mb.types_aspect())),
        ],
        type_aspect(e, xx(e), held, a(e, "key")),
    )


def _const_double(e, cv):
    return e.call(e.eval_builtin("const_numeric_to_double"), e.rec(e.p("xx", xx(e)), e.p("value", cve_value(e, cv))))


def _num_literal(e, bigint):
    """A constant number cast to `number` (its value as a literal) or `bigint` (an integral value, `5n`)."""
    lit = e.if_else(
        e.eq(e.mb.as_(e.v("l"), e.types_double()), e.v("d")),
        to_str(e, e.v("l")),
        to_str(e, e.v("d")),
    )
    checks = []
    if bigint:
        checks.append(
            e.if_only(
                e.not_(e.eq(e.mb.as_(e.v("l"), e.types_double()), e.v("d"))),
                ret_m(e, err_cve(e, loc(e), "js: a bigint literal must be an integer in the 64-bit range")),
            )
        )
        lit = _cat(e, to_str(e, e.v("l")), "n")
    return e.seq(
        e.let("d", _const_double(e, a(e, "cv"))),
        e.let("l", e.mb.as_(e.v("d"), e.mb.types_long())),
        *checks,
        ret_m(e, ok_cve(e, cv_of(e, cve_code(e, a(e, "cv")), _jval(e, outer(e), lit)))),
    )


def _num_types(e, x):
    """`number` (a js number) and `bigint` (a js BigInt), with js's operators on each (`>>>` is number-only, as in
    js). A constant converts to either (`bigint` takes integers); between the two, `n.to_bigint(())` is `BigInt(n)`
    and `b.to_number(())` is `Number(b)`."""
    for obj, desc, marker, conv, conv_js, to_obj, bigint in [
        ("jt_number", "number", "jnumber_m", "to_bigint", "BigInt", "jt_bigint", False),
        ("jt_bigint", "bigint", "jbigint_m", "to_number", "Number", "jt_number", True),
    ]:
        bins = [o for o in NUM_BIN if not (bigint and o == "ushr")]
        _js_type(
            e,
            x,
            obj,
            e.s(desc),
            marker,
            [asp_id(e, "field")] + [op_id(e, o) for o in bins + list(CMP_OPS) + ["neg", "bit_not"]],
            body(e, e.ret(or_b(e, is_equal(e, xx(e), outer(e), src_type(e)), is_const(e, xx(e), src_type(e))))),
            body(
                e,
                e.if_only(is_equal(e, xx(e), outer(e), cve_type(e, a(e, "cv"))), ret_m(e, ok_cve(e, a(e, "cv")))),
                _num_literal(e, bigint),
            ),
            body(e, e.ret(has(e, xx(e), a(e, "other"), marker))),
            e.dstr(desc),
        )
        for o in bins:
            _op_impl(e, x, obj, o, outer(e), lambda a_, b_, o=o: _cat(e, "(", a_, " " + NUM_BIN[o] + " ", b_, ")"))
        _op_impl(e, x, obj, "neg", outer(e), lambda a_, b_: _cat(e, "(- ", a_, ")"), unary=True)
        _op_impl(e, x, obj, "bit_not", outer(e), lambda a_, b_: _cat(e, "(~", a_, ")"), unary=True)
        for o, js_op in CMP_OPS.items():
            _op_impl(e, x, obj, o, _bool_t(e), lambda a_, b_, js_op=js_op: _cat(e, "(", a_, " " + js_op + " ", b_, ")"))
        # `n.to_bigint` / `b.to_number`: the conversion as a method, its data the receiver.
        x.append(
            e.impl_interface(
                e.v(obj),
                asp_iface(e, "field"),
                e.p(
                    "field",
                    body(
                        e,
                        e.if_only(
                            e.not_(e.eq(hf_rec(e, "h_key_str", e.p("xx", xx(e)), e.p("cv", a(e, "key"))), e.s(conv))),
                            ret_m(e, err_cve(e, loc(e), "js: a " + desc + "'s only field is " + conv)),
                        ),
                        e.let("v", _to(e, outer(e), a(e, "value"))),
                        e.ret(
                            ok_cve(
                                e,
                                cv_of(
                                    e,
                                    cve_code(e, e.v("v")),
                                    e.call(
                                        e.eval_builtin("value_object_const"),
                                        e.rec(
                                            e.p(
                                                "type",
                                                mk(e, "jconv", e.p("js", e.s(conv_js)), e.p("to", _unit_t(e, to_obj))),
                                            ),
                                            e.p(
                                                "data",
                                                as_object(e, cv_of(e, code_none(e, loc(e)), cve_value(e, e.v("v")))),
                                            ),
                                        ),
                                    ),
                                ),
                            )
                        ),
                    ),
                ),
                e.p("type_opt", e.option_type_lowered_none()),
                e.p("keys", e.list_new(e.mb.types_constkey(), e.mb.as_(e.s(conv), e.mb.types_constkey()))),
            )
        )
    no = e.mb.as_(e.b(False), bool_t(e))
    self_type(
        e,
        x,
        "jconv",
        e.cat(e.s("js conversion "), in_(e, "js")),
        e.aspect_dispatch(asp_id(e, "function")),
        no,
        cast_to_panic(e),
        no,
        cast_to_panic(e),
        no,
    )
    x.append(
        e.impl_interface(
            e.v("jconv"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("args", _args_of(e, e.list_new(ty(e)))),
                    e.let("v", cv_of(e, cve_code(e, a(e, "function")), cve_value(e, recv_of(e)))),
                    e.ret(
                        ok_cve(
                            e,
                            cv_of(
                                e,
                                cve_code(e, e.v("v")),
                                _jval(e, in_(e, "to"), _cat(e, in_(e, "js"), "(", _jv_expr(e, e.v("v")), ")")),
                            ),
                        )
                    ),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )


def _eq_impls(e, x, obj):
    for o in ["eq", "ne"]:
        _op_impl(e, x, obj, o, _bool_t(e), lambda a_, b_, o=o: _cat(e, "(", a_, " " + CMP_OPS[o] + " ", b_, ")"))


def _scalar_types(e, x):
    """`bool`, `string`, `null`, `undefined` and `void` (a function's absent result: no values)."""
    bool_ids = [op_id(e, o) for o in ["and", "or", "xor", "eq", "ne", "bit_not"]]
    _js_type(
        e,
        x,
        "jt_bool",
        e.s("bool"),
        "jbool_m",
        bool_ids,
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), src_type(e)),
                    has_b(e, xx(e), src_type(e), e.eval_builtin("aspect_bool_const")),
                )
            ),
        ),
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(is_equal(e, xx(e), outer(e), e.v("st")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.ret(
                ok_cve(
                    e,
                    cv_of(
                        e,
                        cve_code(e, a(e, "cv")),
                        _jval(
                            e,
                            outer(e),
                            e.if_else(
                                bim(
                                    e,
                                    e.eval_builtin("aspect_bool_const"),
                                    "get",
                                    lookup_v(e, xx(e), e.v("st"), e.eval_builtin("aspect_bool_const")),
                                    cve_value(e, a(e, "cv")),
                                ),
                                e.dstr("true"),
                                e.dstr("false"),
                            ),
                        ),
                    ),
                )
            ),
        ),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "jbool_m"))),
        e.dstr("boolean"),
    )
    for o, js_op in [("and", "&&"), ("or", "||"), ("xor", "!==")]:
        _op_impl(e, x, "jt_bool", o, outer(e), lambda a_, b_, js_op=js_op: _cat(e, "(", a_, " " + js_op + " ", b_, ")"))
    _eq_impls(e, x, "jt_bool")
    _op_impl(e, x, "jt_bool", "bit_not", outer(e), lambda a_, b_: _cat(e, "(!", a_, ")"), unary=True)

    _js_type(
        e,
        x,
        "jt_string",
        e.s("string"),
        "jstring_m",
        [op_id(e, "add"), asp_id(e, "field")] + [op_id(e, o) for o in CMP_OPS],
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), src_type(e)),
                    has_b(e, xx(e), src_type(e), e.mb.eval_aspect_string_const()),
                )
            ),
        ),
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(is_equal(e, xx(e), outer(e), e.v("st")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.ret(
                ok_cve(
                    e,
                    cv_of(
                        e, cve_code(e, a(e, "cv")), _jval(e, outer(e), hf(e, "h_str_lit", _const_str(e, a(e, "cv"))))
                    ),
                )
            ),
        ),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "jstring_m"))),
        e.dstr("string"),
    )
    _op_impl(e, x, "jt_string", "add", outer(e), lambda a_, b_: _cat(e, "(", a_, " + ", b_, ")"))
    for o, js_op in CMP_OPS.items():
        _op_impl(
            e, x, "jt_string", o, _bool_t(e), lambda a_, b_, js_op=js_op: _cat(e, "(", a_, " " + js_op + " ", b_, ")")
        )
    x.append(
        e.impl_interface(
            e.v("jt_string"),
            asp_iface(e, "field"),
            e.p(
                "field",
                body(
                    e,
                    e.if_only(
                        e.not_(e.eq(hf_rec(e, "h_key_str", e.p("xx", xx(e)), e.p("cv", a(e, "key"))), e.s("length"))),
                        ret_m(e, err_cve(e, loc(e), "js: a string's only field is length")),
                    ),
                    e.let("v", _to(e, outer(e), a(e, "value"))),
                    e.ret(
                        ok_cve(
                            e,
                            cv_of(
                                e,
                                cve_code(e, e.v("v")),
                                _jval(e, _unit_t(e, "jt_number"), _cat(e, _jv_expr(e, e.v("v")), ".length")),
                            ),
                        )
                    ),
                ),
            ),
            e.p("type_opt", e.option_type_lowered_none()),
            e.p("keys", e.list_new(e.mb.types_constkey(), e.mb.as_(e.s("length"), e.mb.types_constkey()))),
        )
    )

    # `null` and `undefined`: their one value is the literal, written `() as js.null`.
    for obj, marker, lit in [("jt_null", "jnull_m", "null"), ("jt_undefined", "jundef_m", "undefined")]:
        empty = body(
            e,
            e.if_only(e.not_(has_b(e, xx(e), src_type(e), asp_iface(e, "tuple"))), ret_m(e, dfalse(e))),
            count_let(e, "ne"),
            count_loop(
                e,
                "ne",
                bim0(e, asp_iface(e, "tuple"), "element_types", lookup_v(e, xx(e), src_type(e), asp_iface(e, "tuple"))),
            ),
            e.ret(e.eq(e.fld(e.v("ne"), "v"), num(e, 0))),
        )
        _js_type(
            e,
            x,
            obj,
            e.s(lit),
            marker,
            [op_id(e, "eq"), op_id(e, "ne")],
            body(e, e.ret(or_b(e, is_equal(e, xx(e), outer(e), src_type(e)), empty))),
            body(
                e,
                e.if_only(is_equal(e, xx(e), outer(e), cve_type(e, a(e, "cv"))), ret_m(e, ok_cve(e, a(e, "cv")))),
                e.ret(ok_cve(e, cv_of(e, cve_code(e, a(e, "cv")), _jval(e, outer(e), e.dstr(lit))))),
            ),
            body(e, e.ret(has(e, xx(e), a(e, "other"), marker))),
            e.dstr(lit),
        )
        _eq_impls(e, x, obj)

    self_type(
        e,
        x,
        "jt_void",
        e.s("void"),
        e.aspect_dispatch(lv(e, "jvoid_m_id")),
        e.mb.as_(e.b(False), bool_t(e)),
        cast_to_panic(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "jvoid_m"))),
    )
    x.append(e.impl_interface(e.v("jt_void"), t(e, "jvoid_m")))


def _same_types(e, xs, ys):
    """Whether the type lists `xs` and `ys` are pairwise equal."""
    return body(
        e,
        count_let(e, "__n1"),
        count_loop(e, "__n1", xs),
        count_let(e, "__n2"),
        count_loop(e, "__n2", ys),
        e.if_only(e.not_(e.eq(e.fld(e.v("__n1"), "v"), e.fld(e.v("__n2"), "v"))), ret_m(e, dfalse(e))),
        e.let("__i", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(
            xs,
            "__x",
            e.seq(
                e.if_only(
                    e.not_(is_equal(e, xx(e), e.v("__x"), e.call_m(ys, "get", e.fld(e.v("__i"), "v")))),
                    ret_m(e, dfalse(e)),
                ),
                e.incr(e.fld(e.v("__i"), "v")),
            ),
        ),
        e.ret(e.not_(dfalse(e))),
    )


def _same_opt_type(e, a_, b_):
    """Whether the optional types `a_` and `b_` are both absent or both the same type."""
    return e.if_else(
        e.fld(a_, "is_some"),
        and_b(e, e.fld(b_, "is_some"), is_equal(e, xx(e), e.fld(a_, "value"), e.fld(b_, "value"))),
        e.not_(e.fld(b_, "is_some")),
    )


def _callable_type(e, x, obj, desc, marker, is_new):
    """A js function (`jt_fn{params, ret}`, `ret` possibly `void`) or constructor (`jt_ctor{params, ret}`): a call
    converts each argument to its parameter's type; a constructor's call is `new`."""
    _js_type(
        e,
        x,
        obj,
        e.s(desc),
        marker,
        [asp_id(e, "function"), op_id(e, "eq"), op_id(e, "ne")],
        body(e, e.ret(is_equal(e, xx(e), outer(e), src_type(e)))),
        body(e, e.ret(ok_cve(e, a(e, "cv")))),
        body(
            e,
            e.if_only(e.not_(has(e, xx(e), a(e, "other"), marker)), ret_m(e, dfalse(e))),
            e.if_only(
                e.not_(is_equal(e, xx(e), in_(e, "ret"), acc(e, xx(e), a(e, "other"), marker, "ret"))),
                ret_m(e, dfalse(e)),
            ),
            e.if_only(
                e.not_(_same_opt_type(e, in_(e, "throws"), acc(e, xx(e), a(e, "other"), marker, "throws"))),
                ret_m(e, dfalse(e)),
            ),
            e.ret(_same_types(e, in_(e, "params"), acc(e, xx(e), a(e, "other"), marker, "params"))),
        ),
        e.dstr("function"),
        [("params", in_(e, "params")), ("ret", in_(e, "ret")), ("throws", in_(e, "throws"))],
    )
    _eq_impls(e, x, obj)
    call = _cat(e, "new " if is_new else "", _jv_expr(e, e.v("f")), "(", e.join(e.fld(e.v("args"), "exprs"), ", "), ")")
    x.append(
        e.impl_interface(
            e.v(obj),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("f", _to(e, outer(e), a(e, "function"))),
                    e.let("args", _args_of(e, in_(e, "params"))),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("f"))),
                    _append_code(e, e.v("out"), e.fld(e.v("args"), "code")),
                    e.if_only(
                        has(e, xx(e), in_(e, "ret"), "jvoid_m"),
                        e.seq(
                            push(e, e.v("out"), _inst(e, _cat(e, call, ";"), loc(e))),
                            ret_m(e, ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                        ),
                    ),
                    e.let("r", _fresh(e, _xmod(e))),
                    push(e, e.v("out"), _inst(e, _cat(e, "var ", e.v("r"), " = ", call, ";"), loc(e))),
                    e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _jval(e, in_(e, "ret"), e.v("r"), True)))),
                ),
            ),
            e.p("exception_type", in_(e, "throws")),
        )
    )


def _slot_type(e, x):
    """A slot: the variable a block's returns store their value in (`jt_slot{name, base}`). It stands in for `base`
    (`_stand_in_dispatch`): its values are read from the variable, and a value cast to it is assigned to the
    variable."""
    self_type(
        e,
        x,
        "jt_slot",
        e.cat(e.s("js slot "), in_(e, "name")),
        _stand_in_dispatch(e, "jslot_m", in_(e, "base")),
        body(e, e.ret(type_can_cast_from(e, xx(e), loc(e), in_(e, "base"), src_type(e)))),
        body(
            e,
            e.let("v", _to(e, in_(e, "base"), a(e, "cv"))),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
            push(e, e.v("out"), _inst(e, _cat(e, in_(e, "name"), " = ", _jv_expr(e, e.v("v")), ";"), loc(e))),
            e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _jval(e, outer(e), in_(e, "name"))))),
        ),
        body(e, e.ret(type_can_cast_from(e, xx(e), loc(e), a(e, "dest_type"), in_(e, "base")))),
        body(
            e,
            e.ret(
                cast_value(
                    e,
                    xx(e),
                    loc(e),
                    a(e, "dest_type"),
                    cv_of(e, cve_code(e, a(e, "cv")), _jval(e, in_(e, "base"), in_(e, "name"))),
                )
            ),
        ),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "jslot_m"),
                    e.eq(acc(e, xx(e), a(e, "other"), "jslot_m", "name"), in_(e, "name")),
                )
            ),
        ),
    )
    x.append(e.impl_interface(e.v("jt_slot"), t(e, "jslot_m"), e.p("name", in_(e, "name"))))


def _global_type(e, x):
    """`jglobal{ty}`: the type of compile-time constants naming a js variable or global of type `ty` (the constant's
    data is the name). It stands in for `ty` (`_stand_in_dispatch`): used, it is that variable, a place."""
    self_type(
        e,
        x,
        "jglobal",
        e.cat(e.s("js global "), ty_desc(e, in_(e, "ty"))),
        rt_dispatch(e, e.mb.types_string(), _stand_in_dispatch(e, "jglobal_m", in_(e, "ty"))),
        can_cast_from_self(e),
        cast_from_self(e),
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), a(e, "dest_type")),
                    type_can_cast_from(e, xx(e), loc(e), a(e, "dest_type"), in_(e, "ty")),
                )
            ),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), a(e, "dest_type")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.ret(
                cast_value(
                    e,
                    xx(e),
                    loc(e),
                    a(e, "dest_type"),
                    cv_of(e, cve_code(e, a(e, "cv")), _jval(e, in_(e, "ty"), hf(e, "h_gref", a(e, "cv")), False, True)),
                )
            ),
        ),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "jglobal_m"),
                    is_equal(e, xx(e), in_(e, "ty"), acc(e, xx(e), a(e, "other"), "jglobal_m", "ty")),
                )
            ),
        ),
    )
    x.append(e.impl_interface(e.v("jglobal"), t(e, "jglobal_m"), e.p("ty", in_(e, "ty"))))
    rt_lift_impl(e, x, "jglobal")
    rt_bind_impl(e, x, "jglobal", e.mb.types_string())
    rt_use_impl(e, x, "jglobal")


def _artifact_id_opt_t(e):
    return e.call(e.mb.types_option(), e.mb.builtin("types", "artifact_id_source"))


def _obj_exporter(e, x):
    """The artifact exporter of declared object types (`jobj_exporter`). An object type may refer to itself through its
    members, so it exports independently, the way the compiler's own recursive types do: the first export reserves
    the type's artifact id (kept on the type) and stores its body, any later one (a cycle back to it) is a reference
    to that id. The body's data is `{name, fields, methods}`, each member `{name, ty}` with `ty` the member type's
    artifact; its exporter is this exporter object. Import creates the type, registers it under its id before
    importing the member types (so a cycle back resolves to it), then attaches the members."""
    art_t = e.mb.builtin("types", "artifact")
    obj_t = e.mb.builtin("types", "object")
    json_t = e.mb.builtin("types", "json_value")
    ix = e.fld(xx(e), "vx", "ix")
    exporter_iface = e.eval_builtin("artifact_exporter")

    def json_str(v):
        return e.call(e.eval_builtin("json_string"), v)

    def member_json(kind):
        return e.seq(
            e.let("__arr", e.list_new(json_t)),
            e.foreach(
                e.call_m(e.v("o"), kind, e.tup()),
                "mb",
                e.seq(
                    e.let("ex", bim(e, e.mb.eval_type(), "artifact_exporter", e.fld(e.v("mb"), "ty"), xx(e))),
                    e.if_only(
                        e.not_(e.fld(e.v("ex"), "is_some")),
                        ret_m(
                            e,
                            e.eresult_err(
                                art_t,
                                loc(e),
                                e.cat(e.s("js: member type of "), e.fld(e.v("mb"), "name"), e.s(" cannot be exported")),
                            ),
                        ),
                    ),
                    e.let(
                        "ma",
                        unwrap_m(
                            e,
                            bim(
                                e,
                                exporter_iface,
                                "export",
                                e.fld(e.v("ex"), "value"),
                                e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", as_object(e, e.fld(e.v("mb"), "ty")))),
                            ),
                            art_t,
                        ),
                    ),
                    push(
                        e,
                        e.v("__arr"),
                        e.call(
                            e.eval_builtin("json_object"),
                            e.map_new(
                                str_(e),
                                json_t,
                                e.p("name", json_str(e.fld(e.v("mb"), "name"))),
                                e.p("ty", e.call(e.eval_builtin("artifact_json_encode"), e.v("ma"))),
                            ),
                        ),
                    ),
                ),
            ),
            e.ret(e.call(e.eval_builtin("json_array"), e.v("__arr"))),
        )

    def json_get(entries, key, kind):
        return e.call(
            e.mb.must_reinterpret(), e.tup(e.call_m(entries, "get", e.s(key)), e.mb.builtin("types", kind))
        )

    x.append(
        e.impl_interface(
            e.v("jobj_exporter"),
            exporter_iface,
            e.p(
                "export",
                body(
                    e,
                    e.let("o", reinterpret(e, a(e, "value"), "jt_obj")),
                    e.let("known", e.call_m(e.v("o"), "artifact_id", e.tup())),
                    e.if_only(
                        e.fld(e.v("known"), "is_some"),
                        ret_m(e, e.eresult_ok(art_t, e.call(e.eval_builtin("artifact_ref"), e.fld(e.v("known"), "value")))),
                    ),
                    e.let("id", bim(e, e.eval_builtin("artifacts"), "reserve_id", e.fld(ix, "artifacts"), e.call_m(ix, "compile_id", e.tup()))),
                    e.call_m(e.v("o"), "set_artifact_id", e.v("id")),
                    e.let("fj", member_json("fields")),
                    e.let("mj", member_json("methods")),
                    e.let(
                        "data",
                        e.call(
                            e.eval_builtin("json_object"),
                            e.map_new(
                                str_(e),
                                json_t,
                                e.p("name", json_str(e.call_m(e.v("o"), "name", e.tup()))),
                                e.p("fields", e.v("fj")),
                                e.p("methods", e.v("mj")),
                            ),
                        ),
                    ),
                    # The body names this exporter object: its own artifact, inline or by reference.
                    # An instance's data exports through its type's `artifact` aspect (as `artifact_exporter_impl`).
                    e.let(
                        "sdc",
                        e.fld(lookup(e, xx(e), lt(e, "jobj_exporter"), asp_iface(e, "dynamic_const")), "value"),
                    ),
                    e.let("scf", bim(e, asp_iface(e, "dynamic_const"), "const_form", e.v("sdc"), xx(e))),
                    e.let(
                        "sx",
                        e.opt_some(
                            exporter_iface,
                            bim0(
                                e,
                                asp_iface(e, "artifact"),
                                "exporter",
                                e.fld(lookup(e, xx(e), e.v("scf"), asp_iface(e, "artifact")), "value"),
                            ),
                        ),
                    ),
                    e.let(
                        "sa",
                        unwrap_m(
                            e,
                            bim(
                                e,
                                exporter_iface,
                                "export",
                                e.fld(e.v("sx"), "value"),
                                e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", as_object(e, outer(e)))),
                            ),
                            art_t,
                        ),
                    ),
                    e.let(
                        "bex",
                        e.match_of(
                            e.call(e.mb.reinterpret(), e.tup(loc(e), e.v("sa"), e.mb.builtin("types", "artifact_inline"))),
                            "__i",
                            None,
                            e.p("ok", e.call(e.eval_builtin("artifact_body_exporter_body"), e.fld(e.v("__i"), "body"))),
                            e.p(
                                "errs",
                                e.call(
                                    e.eval_builtin("artifact_body_exporter_source_ref"),
                                    e.fld(
                                        e.call(
                                            e.mb.must_reinterpret(),
                                            e.tup(e.v("sa"), e.mb.builtin("types", "artifact_ref")),
                                        ),
                                        "id",
                                    ),
                                ),
                            ),
                        ),
                    ),
                    bim(
                        e,
                        e.eval_builtin("artifacts"),
                        "set",
                        e.fld(ix, "artifacts"),
                        e.rec(
                            e.p("id", e.v("id")),
                            e.p("body", e.call(e.eval_builtin("artifact_body"), e.rec(e.p("data", e.v("data")), e.p("exporter", e.v("bex"))))),
                        ),
                    ),
                    e.ret(e.eresult_ok(art_t, e.call(e.eval_builtin("artifact_ref"), e.v("id")))),
                ),
            ),
            e.p(
                "import_from_data",
                body(
                    e,
                    e.let("entries", e.fld(e.call(e.mb.must_reinterpret(), e.tup(a(e, "data"), e.mb.builtin("types", "json_object"))), "entries")),
                    e.let(
                        "o",
                        mk(
                            e,
                            "jt_obj",
                            e.p("name", e.fld(json_get(e.v("entries"), "name", "json_string"), "value")),
                            e.p("fields", e.list_new(_member_t(e))),
                            e.p("methods", e.list_new(_member_t(e))),
                            e.p("artifact_id", a(e, "id")),
                        ),
                    ),
                    e.if_only(
                        e.fld(a(e, "id"), "is_some"),
                        e.call_m(
                            e.fld(ix, "deserialized_artifacts"),
                            "put",
                            e.tup(e.fld(a(e, "id"), "value"), as_object(e, e.v("o"))),
                        ),
                    ),
                    *[
                        e.foreach(
                            e.fld(json_get(e.v("entries"), kind, "json_array"), "elements"),
                            "el",
                            e.seq(
                                e.let(
                                    "me",
                                    e.fld(e.call(e.mb.must_reinterpret(), e.tup(e.v("el"), e.mb.builtin("types", "json_object"))), "entries"),
                                ),
                                e.let(
                                    "mt",
                                    unwrap_m(
                                        e,
                                        e.call(
                                            e.eval_builtin("artifact_import"),
                                            e.rec(
                                                e.p("xx", xx(e)),
                                                e.p("loc", loc(e)),
                                                e.p("artifact", e.call(e.eval_builtin("artifact_json_decode"), e.call_m(e.v("me"), "get", e.s("ty")))),
                                            ),
                                        ),
                                        obj_t,
                                    ),
                                ),
                                e.call_m(
                                    e.v("o"),
                                    "add_" + kind,
                                    e.rec(
                                        e.p("name", e.fld(json_get(e.v("me"), "name", "json_string"), "value")),
                                        e.p("ty", e.call(e.mb.must_reinterpret(), e.tup(e.v("mt"), ty(e)))),
                                    ),
                                ),
                            ),
                        )
                        for kind in ["fields", "methods"]
                    ],
                    e.ret(e.eresult_ok(obj_t, as_object(e, e.v("o")))),
                ),
            ),
        )
    )


def _member_t(e):
    return e.rec(e.p("name", str_(e)), e.p("ty", ty(e)))


def _members_t(e):
    return e.list_type(_member_t(e))


def _key_m(e, label):
    """In a `field` aspect body: binds `key` to the constant field name, else returns an error."""
    return [
        e.let("sk", lookup(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
        e.if_only(
            e.not_(e.fld(e.v("sk"), "is_some")),
            ret_m(e, err_cve(e, loc(e), "js: " + label + " field names are constant strings")),
        ),
        e.let(
            "key",
            bim(e, e.mb.eval_aspect_string_const(), "get", e.fld(e.v("sk"), "value"), cve_value(e, a(e, "key"))),
        ),
    ]


def _method_value(e, recv_cv, name, sig):
    """`recv.name` as a method value: typed `jt_method{name, sig}`, its expression the receiver's."""
    return cv_of(
        e,
        cve_code(e, recv_cv),
        _jval(e, mk(e, "jt_method", e.p("name", name), e.p("sig", sig)), _jv_expr(e, recv_cv)),
    )


def _field_impl(e, x, obj, body_):
    x.append(
        e.impl_interface(
            e.v(obj),
            asp_iface(e, "field"),
            e.p("field", body_),
            e.p("type_opt", e.option_type_lowered_none()),
            e.p("keys", e.list_new(e.mb.types_constkey())),
        )
    )


def _tuple_elems(e, cv, what):
    """Binds `elems` to the elements of the tuple value `cv`, else returns an error."""
    return [
        e.let("tk", lookup(e, xx(e), cve_type(e, cv), asp_iface(e, "tuple"))),
        e.if_only(e.not_(e.fld(e.v("tk"), "is_some")), ret_m(e, err_cve(e, loc(e), "js: " + what + " must be a tuple"))),
        e.let("elems", e.list_new(cve_t(e))),
        e.foreach(
            bim(
                e,
                asp_iface(e, "tuple"),
                "take_elements",
                e.fld(e.v("tk"), "value"),
                e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, cv))),
            ),
            "er",
            push(e, e.v("elems"), unwrap_cve_m(e, e.v("er"))),
        ),
    ]


def _array_type(e, x):
    """`js.array{elem}`: a js Array of `elem`. `a.length` (a number), `a[i]` (an element, a place), `a.push(v)`, and
    `foreach` (`for (var x of a)`); a tuple of elements converts to an array literal."""
    elem = in_(e, "elem")
    _js_type(
        e,
        x,
        "jt_array",
        e.cat(e.s("array("), ty_desc(e, elem), e.s(")")),
        "jarray_m",
        [asp_id(e, "field"), asp_id(e, "iterable"), op_id(e, "eq"), op_id(e, "ne")],
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), src_type(e)), ret_m(e, e.not_(dfalse(e)))),
            e.let("tk", lookup(e, xx(e), src_type(e), asp_iface(e, "tuple"))),
            e.if_only(e.not_(e.fld(e.v("tk"), "is_some")), ret_m(e, dfalse(e))),
            e.foreach(
                bim0(e, asp_iface(e, "tuple"), "element_types", e.fld(e.v("tk"), "value")),
                "et",
                e.if_only(
                    e.not_(type_can_cast_from(e, xx(e), loc(e), elem, e.v("et"))),
                    ret_m(e, dfalse(e)),
                ),
            ),
            e.ret(e.not_(dfalse(e))),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), cve_type(e, a(e, "cv"))), ret_m(e, ok_cve(e, a(e, "cv")))),
            *_tuple_elems(e, a(e, "cv"), "an array literal"),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, a(e, "cv"))),
            e.let("parts", e.list_new(str_(e))),
            e.foreach(
                e.v("elems"),
                "ec",
                e.seq(
                    e.let("ev", _to(e, elem, e.v("ec"))),
                    _append_code(e, e.v("out"), cve_code(e, e.v("ev"))),
                    push(e, e.v("parts"), _jv_expr(e, e.v("ev"))),
                ),
            ),
            e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _jval(e, outer(e), _cat(e, "[", e.join(e.v("parts"), ", "), "]"))))),
        ),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "jarray_m"),
                    is_equal(e, xx(e), elem, acc(e, xx(e), a(e, "other"), "jarray_m", "elem")),
                )
            ),
        ),
        e.dstr("object"),
        [("elem", elem)],
    )
    _eq_impls(e, x, "jt_array")
    _field_impl(
        e,
        x,
        "jt_array",
        body(
            e,
            e.let("v", _to(e, outer(e), a(e, "value"))),
            e.let("sk", lookup(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
            e.if_only(
                e.not_(e.fld(e.v("sk"), "is_some")),
                e.seq(
                    e.let("i", _to(e, _unit_t(e, "jt_number"), a(e, "key"))),
                    ret_m(
                        e,
                        ok_cve(
                            e,
                            cv_of(
                                e,
                                _code_of(e, _seq_insts(e, e.v("v"), e.v("i"))),
                                _jval(e, elem, _cat(e, _jv_expr(e, e.v("v")), "[", _jv_expr(e, e.v("i")), "]"), False, True),
                            ),
                        ),
                    ),
                ),
            ),
            e.let(
                "key",
                bim(e, e.mb.eval_aspect_string_const(), "get", e.fld(e.v("sk"), "value"), cve_value(e, a(e, "key"))),
            ),
            e.if_only(
                e.eq(e.v("key"), e.s("length")),
                ret_m(
                    e,
                    ok_cve(
                        e,
                        cv_of(
                            e,
                            cve_code(e, e.v("v")),
                            _jval(e, _unit_t(e, "jt_number"), _cat(e, _jv_expr(e, e.v("v")), ".length"), False, True),
                        ),
                    ),
                ),
            ),
            e.if_only(
                e.eq(e.v("key"), e.s("push")),
                ret_m(
                    e,
                    ok_cve(
                        e,
                        _method_value(
                            e,
                            e.v("v"),
                            e.s("push"),
                            mk(
                                e,
                                "jt_fn",
                                e.p("params", e.list_new(ty(e), elem)),
                                e.p("ret", _unit_t(e, "jt_number")),
                                e.p("throws", e.opt_none(ty(e))),
                            ),
                        ),
                    ),
                ),
            ),
            e.ret(err_cve(e, loc(e), e.cat(e.s("js: an array has no field "), e.v("key")))),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("jt_array"),
            asp_iface(e, "iterable"),
            e.p("element_type", elem),
            e.p("loop_binding", mk(e, "jbinding", e.p("name", _fresh(e, _xmod_must(e, e.v("arg")))), e.p("ty", elem))),
            e.p(
                "element_access",
                ok_cve(
                    e,
                    cv_of(
                        e,
                        code_none(e, loc(e)),
                        _jval(e, elem, e.call_m(reinterpret(e, a(e, "loop"), "jbinding"), "name", e.tup())),
                    ),
                ),
            ),
            e.p(
                "foreach",
                body(
                    e,
                    e.let("arr", _to(e, outer(e), a(e, "base"))),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("arr"))),
                    e.let("name", e.call_m(reinterpret(e, a(e, "loop"), "jbinding"), "name", e.tup())),
                    push(
                        e,
                        e.v("out"),
                        _inst(e, _cat(e, "for (var ", e.v("name"), " of ", _jv_expr(e, e.v("arr")), ") {"), loc(e)),
                    ),
                    e.let("bi", _insts_new(e)),
                    _append_code(e, e.v("bi"), a(e, "element_bind")),
                    _append_code(e, e.v("bi"), cve_code(e, a(e, "body"))),
                    _push_indented(e, e.v("bi"), e.dstr(""), "  "),
                    push(e, e.v("out"), _inst(e, e.s("}"), loc(e))),
                    e.ret(ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                ),
            ),
        )
    )


def _seq_insts(e, *cvs):
    """The statements of the code values `cvs`, in order."""
    return e.seq(
        e.let("__o", _insts_new(e)),
        *[_append_code(e, e.v("__o"), cve_code(e, cv)) for cv in cvs],
        e.ret(e.v("__o")),
    )


def _method_type(e, x):
    """`jt_method{name, sig}`: the method `name` of a receiver, a value whose expression is the receiver's; calling it
    is `recv.name(args)` (so `this` is the receiver), and binding it binds the receiver."""
    _js_type(
        e,
        x,
        "jt_method",
        e.cat(e.s("method "), in_(e, "name")),
        "jmethod_m",
        [asp_id(e, "function")],
        body(e, e.ret(is_equal(e, xx(e), outer(e), src_type(e)))),
        body(e, e.ret(ok_cve(e, a(e, "cv")))),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "jmethod_m"),
                    and_b(
                        e,
                        e.eq(acc(e, xx(e), a(e, "other"), "jmethod_m", "name"), in_(e, "name")),
                        is_equal(e, xx(e), in_(e, "sig"), acc(e, xx(e), a(e, "other"), "jmethod_m", "sig")),
                    ),
                )
            ),
        ),
        e.dstr("method"),
        [("name", in_(e, "name")), ("sig", in_(e, "sig"))],
    )
    sig = in_(e, "sig")
    call = _cat(
        e, _jv_expr(e, e.v("f")), ".", in_(e, "name"), "(", e.join(e.fld(e.v("args"), "exprs"), ", "), ")"
    )
    x.append(
        e.impl_interface(
            e.v("jt_method"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("f", _to(e, outer(e), a(e, "function"))),
                    e.let("ret", acc(e, xx(e), sig, "jfn_m", "ret")),
                    e.let("args", _args_of(e, acc(e, xx(e), sig, "jfn_m", "params"))),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("f"))),
                    _append_code(e, e.v("out"), e.fld(e.v("args"), "code")),
                    e.if_only(
                        has(e, xx(e), e.v("ret"), "jvoid_m"),
                        e.seq(
                            push(e, e.v("out"), _inst(e, _cat(e, call, ";"), loc(e))),
                            ret_m(e, ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                        ),
                    ),
                    e.let("r", _fresh(e, _xmod(e))),
                    push(e, e.v("out"), _inst(e, _cat(e, "var ", e.v("r"), " = ", call, ";"), loc(e))),
                    e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _jval(e, e.v("ret"), e.v("r"), True)))),
                ),
            ),
            e.p("exception_type", acc(e, xx(e), in_(e, "sig"), "jfn_m", "throws")),
        )
    )


def _member_of(e, members, name_expr, bind):
    """Binds `bind` (a list of zero or one types) to the type of the member `name_expr` in `members`."""
    return [
        e.let(bind, e.list_new(ty(e))),
        e.foreach(
            members,
            "__mb",
            e.if_only(e.eq(e.fld(e.v("__mb"), "name"), name_expr), push(e, e.v(bind), e.fld(e.v("__mb"), "ty"))),
        ),
    ]


def _count(e, list_):
    return e.seq(count_let(e, "__c"), count_loop(e, "__c", list_), e.ret(e.fld(e.v("__c"), "v")))


def _object_type(e, x):
    """`js.object{name}`: a declared js object type (nominal: its identity is its name), its members attached by
    `js.members{object, fields, methods}` (so declarations can refer to each other). `o.f` reads a field (a place),
    `o.m(args)` calls a method with `o` as `this`; a record with exactly the declared fields converts to an object
    literal."""
    fields = in_(e, "fields")
    _js_type(
        e,
        x,
        "jt_obj",
        in_(e, "name"),
        "jobj_m",
        [asp_id(e, "field"), op_id(e, "eq"), op_id(e, "ne")],
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), src_type(e)), ret_m(e, e.not_(dfalse(e)))),
            e.let("rk", lookup(e, xx(e), src_type(e), asp_iface(e, "record"))),
            e.if_only(e.not_(e.fld(e.v("rk"), "is_some")), ret_m(e, dfalse(e))),
            e.let("rn", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                bim0(e, asp_iface(e, "record"), "field_types", e.fld(e.v("rk"), "value")),
                "en",
                e.seq(
                    e.incr(e.fld(e.v("rn"), "v")),
                    *_member_of(e, fields, key_str(e, e.fld(e.v("en"), "key")), "ft"),
                    e.if_only(e.eq(_count(e, e.v("ft")), e.int_of(0)), ret_m(e, dfalse(e))),
                ),
            ),
            e.ret(e.eq(e.fld(e.v("rn"), "v"), _count(e, fields))),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), cve_type(e, a(e, "cv"))), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.let("rk", lookup(e, xx(e), cve_type(e, a(e, "cv")), asp_iface(e, "record"))),
            e.let(
                "rf",
                bim(
                    e,
                    asp_iface(e, "record"),
                    "take_fields",
                    e.fld(e.v("rk"), "value"),
                    e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, a(e, "cv")))),
                ),
            ),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, a(e, "cv"))),
            e.let("parts", e.list_new(str_(e))),
            e.foreach(
                fields,
                "fd",
                e.seq(
                    e.let("fv", _to(e, e.fld(e.v("fd"), "ty"), unwrap_cve_m(e, e.call_m(e.v("rf"), "get", e.fld(e.v("fd"), "name"))))),
                    _append_code(e, e.v("out"), cve_code(e, e.v("fv"))),
                    push(e, e.v("parts"), _cat(e, e.fld(e.v("fd"), "name"), ": ", _jv_expr(e, e.v("fv")))),
                ),
            ),
            e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _jval(e, outer(e), _cat(e, "{", e.join(e.v("parts"), ", "), "}"))))),
        ),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "jobj_m"),
                    e.eq(acc(e, xx(e), a(e, "other"), "jobj_m", "name"), in_(e, "name")),
                )
            ),
        ),
        e.dstr("object"),
        [("name", in_(e, "name"))],
        e.opt_some(e.eval_builtin("artifact_exporter"), e.mb.as_(mk_arg(e, "jobj_exporter", e.tup()), e.eval_builtin("artifact_exporter"))),
    )
    _eq_impls(e, x, "jt_obj")
    _field_impl(
        e,
        x,
        "jt_obj",
        body(
            e,
            *_key_m(e, "an object's"),
            e.let("v", _to(e, outer(e), a(e, "value"))),
            *_member_of(e, fields, e.v("key"), "ft"),
            e.foreach(
                e.v("ft"),
                "t0",
                ret_m(
                    e,
                    ok_cve(
                        e,
                        cv_of(e, cve_code(e, e.v("v")), _jval(e, e.v("t0"), _cat(e, _jv_expr(e, e.v("v")), ".", e.v("key")), False, True)),
                    ),
                ),
            ),
            *_member_of(e, in_(e, "methods"), e.v("key"), "mt"),
            e.foreach(e.v("mt"), "t0", ret_m(e, ok_cve(e, _method_value(e, e.v("v"), e.v("key"), e.v("t0"))))),
            e.ret(err_cve(e, loc(e), e.cat(e.s("js: "), in_(e, "name"), e.s(" has no member "), e.v("key")))),
        ),
    )
    accessor(e, x, "jt_obj", "name", str_(e))
    accessor(e, x, "jt_obj", "fields", _members_t(e))
    accessor(e, x, "jt_obj", "methods", _members_t(e))
    accessor(e, x, "jt_obj", "artifact_id", _artifact_id_opt_t(e))
    x.append(
        e.method_impl(
            e.v("jt_obj"),
            "set_artifact_id",
            e.mb.builtin("types", "artifact_id_source"),
            e.option_type_none(),
            e.stage(e.mb.set(in_(e, "artifact_id"), e.opt_some(e.mb.builtin("types", "artifact_id_source"), e.v("arg")))),
        )
    )
    _obj_exporter(e, x)
    for kind in ["fields", "methods"]:
        x.append(
            e.method_impl(
                e.v("jt_obj"),
                "add_" + kind,
                _member_t(e),
                e.option_type_none(),
                e.stage(push(e, in_(e, kind), e.v("arg"))),
            )
        )


# The js runtime tags a union tells its members by, and each one's test (`%` is the value's expression).
UNION_TESTS = {
    "number": 'typeof % === "number"',
    "bigint": 'typeof % === "bigint"',
    "boolean": 'typeof % === "boolean"',
    "string": 'typeof % === "string"',
    "function": 'typeof % === "function"',
    "null": "% === null",
    "undefined": "% === undefined",
    "object": 'typeof % === "object" && % !== null',
}


def _union_test(e, tag, x_):
    """The js test that a union value (the expression `x_`) holds the member of runtime tag `tag`."""
    out = None
    for t_, text in reversed(list(UNION_TESTS.items())):
        parts = text.split("%")
        expr = [parts[0]]
        for rest in parts[1:]:
            expr.append(x_)
            expr.append(rest)
        piece = _cat(e, "(", *expr, ")")
        out = piece if out is None else e.if_else(e.eq(tag, e.s(t_)), piece, out)
    return out


def _union_type(e, x):
    """`js.union{k: T, ...}`: an untagged js union, its members told apart by their runtime tags (one member per
    tag). A member's value converts to it as is (a value converts when exactly one member takes it); `match` tests
    the tag (`typeof`, `=== null`, ...) and reads the member."""
    variants = in_(e, "variants")
    _js_type(
        e,
        x,
        "jt_union",
        e.seq(
            e.let("__ds", e.list_new(str_(e))),
            e.foreach(variants, "__v", push(e, e.v("__ds"), ty_desc(e, e.fld(e.v("__v"), "ty")))),
            e.ret(e.join(e.v("__ds"), " | ")),
        ),
        "junion_m",
        [e.eval_builtin("aspect_union_id"), op_id(e, "eq"), op_id(e, "ne")],
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), src_type(e)), ret_m(e, e.not_(dfalse(e)))),
            e.let("n", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                variants,
                "vr",
                e.if_only(
                    type_can_cast_from(e, xx(e), loc(e), e.fld(e.v("vr"), "ty"), src_type(e)), e.incr(e.fld(e.v("n"), "v"))
                ),
            ),
            e.ret(e.eq(e.fld(e.v("n"), "v"), e.int_of(1))),
        ),
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(is_equal(e, xx(e), outer(e), e.v("st")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.foreach(
                variants,
                "vr",
                e.if_only(
                    type_can_cast_from(e, xx(e), loc(e), e.fld(e.v("vr"), "ty"), e.v("st")),
                    e.seq(
                        e.let("mv", _to(e, e.fld(e.v("vr"), "ty"), a(e, "cv"))),
                        ret_m(e, ok_cve(e, cv_of(e, cve_code(e, e.v("mv")), _jval(e, outer(e), _jv_expr(e, e.v("mv")))))),
                    ),
                ),
            ),
            e.ret(err_cve(e, loc(e), "js: no member of the union takes this value")),
        ),
        body(
            e,
            e.if_only(e.not_(has(e, xx(e), a(e, "other"), "junion_m")), ret_m(e, dfalse(e))),
            e.let("ov", acc(e, xx(e), a(e, "other"), "junion_m", "variants")),
            e.if_only(e.not_(e.eq(_count(e, variants), _count(e, e.v("ov")))), ret_m(e, dfalse(e))),
            e.let("i", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                variants,
                "vr",
                e.seq(
                    e.let("o0", e.call_m(e.v("ov"), "get", e.fld(e.v("i"), "v"))),
                    e.if_only(
                        or_b(
                            e,
                            e.not_(e.eq(e.fld(e.v("vr"), "name"), e.fld(e.v("o0"), "name"))),
                            e.not_(is_equal(e, xx(e), e.fld(e.v("vr"), "ty"), e.fld(e.v("o0"), "ty"))),
                        ),
                        ret_m(e, dfalse(e)),
                    ),
                    e.incr(e.fld(e.v("i"), "v")),
                ),
            ),
            e.ret(e.not_(dfalse(e))),
        ),
        e.dstr("union"),
        [("variants", variants)],
    )
    _eq_impls(e, x, "jt_union")

    def variant_ty(idx):
        return e.fld(e.call_m(variants, "get", idx), "ty")

    x.append(
        e.impl_interface(
            e.v("jt_union"),
            e.eval_builtin("aspect_union"),
            e.p(
                "variants",
                e.seq(
                    e.let("__vs", e.list_new(e.mb.builtin("types", "aspect_union_variant"))),
                    e.foreach(
                        variants,
                        "__v",
                        push(
                            e,
                            e.v("__vs"),
                            e.call(
                                e.eval_builtin("aspect_union_variant"),
                                e.rec(
                                    e.p("key", e.mb.as_(e.fld(e.v("__v"), "name"), e.mb.types_constkey())),
                                    e.p("type", e.fld(e.v("__v"), "ty")),
                                ),
                            ),
                        ),
                    ),
                    e.ret(e.v("__vs")),
                ),
            ),
            e.p(
                "test",
                body(
                    e,
                    e.let("b", _to(e, outer(e), a(e, "base"))),
                    e.ret(
                        ok_cve(
                            e,
                            cv_of(
                                e,
                                cve_code(e, e.v("b")),
                                _jval(
                                    e,
                                    _bool_t(e),
                                    _union_test(e, _tag(e, xx(e), variant_ty(a(e, "variant_index"))), _jv_expr(e, e.v("b"))),
                                ),
                            ),
                        )
                    ),
                ),
            ),
            e.p(
                "extract",
                body(
                    e,
                    e.let("b", _to(e, outer(e), a(e, "base"))),
                    e.ret(
                        ok_cve(
                            e,
                            cv_of(e, cve_code(e, e.v("b")), _jval(e, variant_ty(a(e, "variant_index")), _jv_expr(e, e.v("b")))),
                        )
                    ),
                ),
            ),
        )
    )


def _match_hook(e):
    """`match`: the base's code once, then `_arms_layout` over the cases' tags (each test a `bool`); the else arm is
    the fallback or, without one, the last case (the match is exhaustive, so it needs no test)."""
    fb = a(e, "fallback")
    return _arms_layout(
        e,
        e.if_only(e.not_(cve_has(e, a(e, "base"))), ret_m(e, err_cve(e, loc(e), "js: match: the value has no value"))),
        _append_code(e, e.v("out"), cve_code(e, a(e, "base"))),
        e.let("arms", e.list_new(e.rec(e.p("condition", cve_t(e)), e.p("body", cve_t(e))))),
        count_let(e, "ncase"),
        count_loop(e, "ncase", a(e, "cases")),
        e.let("elsm", e.map_new(str_(e), cve_t(e))),
        e.let("ci0", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(
            a(e, "cases"),
            "cs",
            e.seq(
                e.incr(e.fld(e.v("ci0"), "v")),
                e.if_else(
                    and_b(e, e.not_(e.fld(fb, "is_some")), e.eq(e.fld(e.v("ci0"), "v"), e.fld(e.v("ncase"), "v"))),
                    e.call_m(e.v("elsm"), "put", e.tup(e.s("else"), e.fld(e.v("cs"), "body"))),
                    push(
                        e,
                        e.v("arms"),
                        e.rec(e.p("condition", e.fld(e.v("cs"), "test")), e.p("body", e.fld(e.v("cs"), "body"))),
                    ),
                ),
            ),
        ),
        e.let("els", e.if_else(e.fld(fb, "is_some"), fb, e.opt_some(cve_t(e), e.call_m(e.v("elsm"), "get", e.s("else"))))),
    )


def _lbl(e, key, mod=None):
    """The label of a block's jump key (minted on first use) in `mod` (by default the target's module)."""
    return e.call_m(in_(e, "mod") if mod is None else mod, "label_of", key)


def _exc_transfer(e, out, next_opt, val, mod=None):
    """Appends to `out` the transfer of the exception `val` (an expression): to the landing `next_opt` (its exception
    variable `<label>x`, then `break`), or, with none, out of the function (`throw`)."""
    return e.if_else(
        e.fld(next_opt, "is_some"),
        e.seq(
            e.let("__nl", _lbl(e, e.fld(next_opt, "value"), mod)),
            push(e, out, _inst(e, _cat(e, "var ", e.v("__nl"), "x = ", val, ";"), loc(e))),
            push(e, out, _inst(e, _cat(e, "break ", e.v("__nl"), ";"), loc(e))),
        ),
        push(e, out, _inst(e, _cat(e, "throw ", val, ";"), loc(e))),
    )


def _exc_hooks(e):
    """The target's exception hooks. Every transfer the core makes is forward, to a landing later in the same or an
    enclosing region, so each is a `break` to the landing's labeled block (`h_resolve`), carrying the exception in
    the landing's variable `<label>x`. A guarded region is a js `try` whose `catch` makes that transfer (rethrowing a
    panic, `Panic$`: panics are not exceptions)."""
    opt_code_t = e.call(e.mb.types_option(), code_t(e))
    return [
        e.p(
            "jump",
            e.eresult_ok(
                code_t(e),
                _code_of(e, e.list_new(lt(e, "jinst"), _inst(e, _cat(e, "break ", _lbl(e, a(e, "dest")), ";"), loc(e)))),
            ),
        ),
        e.p(
            "guarded",
            body(
                e,
                e.let("ins", hf(e, "h_insts", a(e, "inner"))),
                count_let(e, "ni"),
                count_loop(e, "ni", e.v("ins")),
                e.if_only(e.eq(e.fld(e.v("ni"), "v"), num(e, 0)), ret_m(e, e.eresult_ok(code_t(e), a(e, "inner")))),
                e.let("d", _lbl(e, a(e, "dest"))),
                e.let("ce", _fresh(e, in_(e, "mod"))),
                e.let("out", _insts_new(e)),
                push(e, e.v("out"), _inst(e, e.s("try {"), loc(e))),
                _push_indented(e, e.v("ins"), e.dstr(""), "  "),
                push(e, e.v("out"), _inst(e, _cat(e, "} catch (", e.v("ce"), ") {"), loc(e))),
                push(
                    e,
                    e.v("out"),
                    _inst(e, _cat(e, "  if (", e.v("ce"), " instanceof Panic$) throw ", e.v("ce"), ";"), loc(e)),
                ),
                push(e, e.v("out"), _inst(e, _cat(e, "  var ", e.v("d"), "x = ", e.v("ce"), ";"), loc(e))),
                push(e, e.v("out"), _inst(e, _cat(e, "  break ", e.v("d"), ";"), loc(e))),
                push(e, e.v("out"), _inst(e, e.s("}"), loc(e))),
                e.ret(e.eresult_ok(code_t(e), _code_of(e, e.v("out")))),
            ),
        ),
        # The landing of a call's exception: the callee's exception, converted to the caller's, moves on.
        e.p(
            "cast_exception",
            body(
                e,
                e.let("k", _lbl(e, a(e, "key"))),
                e.let("out", _insts_new(e)),
                push(e, e.v("out"), _label_inst(e, e.v("k"), loc(e))),
                e.let(
                    "v",
                    e.match_of(
                        cast_value(
                            e,
                            xx(e),
                            loc(e),
                            a(e, "caller_exc"),
                            cv_of(e, code_none(e, loc(e)), _jval(e, a(e, "callee_exc"), _cat(e, e.v("k"), "x"))),
                        ),
                        "__r",
                        None,
                        e.p("ok", e.v("__r")),
                        e.p("errs", ret_m(e, e.eresult_errs(opt_code_t, e.v("__r")))),
                    ),
                ),
                # A conversion without code only changes the static type (the js value is the same): no block, so
                # the core guards the call straight to `next`, or not at all when there is no `next`.
                e.if_only(
                    e.not_(is_target_code(e, cve_code(e, e.v("v")))),
                    ret_m(e, e.eresult_ok(opt_code_t, e.opt_none(code_t(e)))),
                ),
                _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                _exc_transfer(e, e.v("out"), a(e, "next"), _jv_expr(e, e.v("v"))),
                e.ret(e.eresult_ok(opt_code_t, e.opt_some(code_t(e), _code_of(e, e.v("out"))))),
            ),
        ),
        # An unwinding cleanup: its landing, the drops, then on to the parent landing (or out of the function).
        e.p(
            "exc_cleanup",
            body(
                e,
                e.let("k", _lbl(e, a(e, "key"))),
                e.let("out", _insts_new(e)),
                push(e, e.v("out"), _label_inst(e, e.v("k"), loc(e))),
                _append_code(e, e.v("out"), a(e, "cleanup")),
                _exc_transfer(e, e.v("out"), a(e, "parent"), _cat(e, e.v("k"), "x")),
                e.ret(e.eresult_ok(code_t(e), _code_of(e, e.v("out")))),
            ),
        ),
        # A cleanup on a block exit's way out (a `finally`): the carried value already sits in its slot.
        e.p(
            "exit_trampoline",
            body(
                e,
                e.if_only(
                    e.fld(a(e, "argument"), "is_some"),
                    e.mb.panic(e.s("js target: exits carry their values in slots, not as arguments")),
                ),
                e.let("out", _insts_new(e)),
                push(e, e.v("out"), _label_inst(e, _lbl(e, a(e, "key")), loc(e))),
                _append_code(e, e.v("out"), a(e, "cleanup")),
                push(e, e.v("out"), _inst(e, _cat(e, "break ", _lbl(e, a(e, "next")), ";"), loc(e))),
                e.ret(e.eresult_ok(code_t(e), _code_of(e, e.v("out")))),
            ),
        ),
        e.p(
            "initial_bind",
            e.eresult_ok(
                e.mb.eval_binding(),
                e.mb.as_(
                    mk(e, "jbinding", e.p("name", _fresh(e, in_(e, "mod"))), e.p("ty", a(e, "type"))),
                    e.mb.eval_binding(),
                ),
            ),
        ),
        e.p("try_catch_finally", _try_hook(e)),
    ]


def _try_hook(e):
    """`try`: the body, then the catch (the landing of the try's exceptions: its payload binding takes the landing's
    exception) and the join both arms fall to, then the finally code of the normal path. A valued try's result is a
    variable assigned in each arm, typed by the first valued one (`_arm_stmts`)."""
    catch_ = a(e, "catch")
    return body(
        e,
        e.let("mod", in_(e, "mod")),
        e.let("join", e.call_m(e.v("mod"), "label_fresh", e.tup())),
        e.let(
            "st",
            e.rec(
                e.p("ended", e.int_of(1)),
                e.p("has", e.int_of(0)),
                e.p("novalue", e.int_of(0)),
                e.p("typed", e.int_of(0)),
                e.p("res", _fresh(e, e.v("mod"))),
            ),
        ),
        e.let("rt", e.list_new(ty(e))),
        e.let("bo", _insts_new(e)),
        e.let("b", a(e, "body")),
        _arm_stmts(e, "b"),
        e.if_only(
            e.not_(cve_ended(e, a(e, "body"))),
            push(e, e.v("bo"), _inst(e, _cat(e, "break ", e.v("join"), ";"), loc(e))),
        ),
        e.if_only(
            e.fld(catch_, "is_some"),
            e.seq(
                e.let("cc", e.fld(catch_, "value")),
                e.let("h", _lbl(e, e.fld(a(e, "catch_handler"), "value"))),
                push(e, e.v("bo"), _label_inst(e, e.v("h"), loc(e))),
                push(
                    e,
                    e.v("bo"),
                    _inst(
                        e,
                        _cat(
                            e,
                            "var ",
                            e.call_m(reinterpret(e, e.fld(e.v("cc"), "binding"), "jbinding"), "name", e.tup()),
                            " = ",
                            e.v("h"),
                            "x;",
                        ),
                        loc(e),
                    ),
                ),
                e.let("cb", e.fld(e.v("cc"), "body")),
                _arm_stmts(e, "cb"),
                e.if_only(
                    e.not_(cve_ended(e, e.v("cb"))),
                    push(e, e.v("bo"), _inst(e, _cat(e, "break ", e.v("join"), ";"), loc(e))),
                ),
            ),
        ),
        push(e, e.v("bo"), _label_inst(e, e.v("join"), loc(e))),
        e.if_only(e.fld(a(e, "finally_normal"), "is_some"), _append_code(e, e.v("bo"), e.fld(a(e, "finally_normal"), "value"))),
        e.if_only(
            e.eq(e.fld(e.v("st"), "ended"), num(e, 1)),
            ret_m(e, ok_cve(e, e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("bo"))))),
        ),
        e.if_only(e.eq(e.fld(e.v("st"), "has"), num(e, 0)), ret_m(e, ok_cve(e, cv_no(e, _code_of(e, e.v("bo")))))),
        e.if_only(
            e.eq(e.fld(e.v("st"), "novalue"), num(e, 1)),
            ret_m(e, err_cve(e, loc(e), "try: the body and the catch must both yield a value or neither")),
        ),
        e.let("all", _insts_new(e)),
        push(e, e.v("all"), _inst(e, _cat(e, "var ", e.fld(e.v("st"), "res"), ";"), loc(e))),
        e.foreach(e.v("bo"), "i0", push(e, e.v("all"), e.v("i0"))),
        e.ret(
            ok_cve(
                e,
                cv_of(
                    e,
                    _code_of(e, e.v("all")),
                    _jval(e, e.call_m(e.v("rt"), "get", e.int_of(0)), e.fld(e.v("st"), "res")),
                ),
            )
        ),
    )


def _raise_types(e, x):
    """`throw` and `panic`: callable types whose value is `()` cast to them. `throw(v)` raises `v`, converted to the
    enclosing function's exception type, along the core's exception destination (`eval.exc_dest`: the unwinding
    cleanups, then the catch or out of the function), as the dynamic target's `throw` does. `panic(message)` throws a
    `Panic$` error that no catch takes."""
    for obj, marker, desc in [("jthrow", "jthrow_m", "js throw"), ("jpanic", "jpanic_m", "js panic")]:
        self_type(
            e,
            x,
            obj,
            e.s(desc),
            e.aspect_dispatch(lv(e, marker + "_id"), asp_id(e, "function"), asp_id(e, "bind")),
            tm.can_cast_from_unit(e),
            tm.cast_from_empty(e),
            no_cast_to(e),
            cast_to_panic(e),
            body(e, e.ret(has(e, xx(e), a(e, "other"), marker))),
        )
        x.append(e.impl_interface(e.v(obj), t(e, marker)))
        x.append(e.impl_interface(e.v(obj), e.mb.eval_aspect_bind(), e.p("bind", tm.bind_empty(e, "jebinding"))))
    exc = e.fld(xx(e), "current_exception_type")
    x.append(
        e.impl_interface(
            e.v("jthrow"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.if_only(
                        e.not_(e.fld(exc, "is_some")),
                        ret_m(e, err_cve(e, loc(e), "js throw: the enclosing function declares no exception type")),
                    ),
                    e.let("v", _to(e, e.fld(exc, "value"), a(e, "argument"))),
                    e.let(
                        "dest",
                        unwrap_cve_m(e, e.call(e.eval_builtin("exc_dest"), e.rec(e.p("xx", xx(e)), e.p("loc", loc(e))))),
                    ),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                    _exc_transfer(e, e.v("out"), e.v("dest"), _jv_expr(e, e.v("v")), _xmod(e)),
                    e.ret(ok_cve(e, e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("out"))))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )
    x.append(
        e.impl_interface(
            e.v("jpanic"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("v", _to(e, _string_t(e), a(e, "argument"))),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                    push(e, e.v("out"), _inst(e, _cat(e, "throw new Panic$(", _jv_expr(e, e.v("v")), ");"), loc(e))),
                    e.ret(ok_cve(e, e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("out"))))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )


def _xmod_must(e, xx_):
    """The module of the target in the context `xx_` (always the js target in a js type's aspect)."""
    return e.call_m(e.call(e.mb.must_reinterpret(), e.tup(e.fld(xx_, "target"), lt(e, "jtarget"))), "mod", e.tup())


def module(e):
    x = []
    entries = []
    for b in range(256):
        if b == ord('"'):
            text = '\\"'
        elif b == ord("\\"):
            text = "\\\\"
        elif b == ord("\n"):
            text = "\\n"
        elif b == ord("\r"):
            text = "\\r"
        elif b == ord("\t"):
            text = "\\t"
        elif b < 32 or b == 127:
            text = "\\u%04x" % b
        else:
            text = ""
        entries.append(e.p(str(b), e.s(text)))
    escape_table = e.map_new(str_(e), str_(e), *entries)
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("srcmap", e.import_local("srcmap", srcmap.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    def_iface(e, x, "jtype_m", e.p("tag", str_(e)), e.p("base", ty(e)))
    for m in ["jnumber_m", "jbigint_m", "jbool_m", "jstring_m", "jnull_m", "jundef_m", "jvoid_m"]:
        def_iface(e, x, m)
    for m in ["jfn_m", "jctor_m"]:
        def_iface(e, x, m, e.p("params", e.list_type(ty(e))), e.p("ret", ty(e)), e.p("throws", e.call(e.mb.types_option(), ty(e))))
    def_iface(e, x, "jglobal_m", e.p("ty", ty(e)))
    def_iface(e, x, "jarray_m", e.p("elem", ty(e)))
    def_iface(e, x, "jmethod_m", e.p("name", str_(e)), e.p("sig", ty(e)))
    def_iface(e, x, "jobj_m", e.p("name", str_(e)))
    def_iface(e, x, "junion_m", e.p("variants", _members_t(e)))
    def_iface(e, x, "jgfn_m", e.p("kind", int_t(e)))
    def_iface(e, x, "jinst_m")
    def_iface(e, x, "jlabel_m")
    def_iface(e, x, "jmod_m")
    def_iface(e, x, "jbinding_m")
    def_iface(e, x, "jslot_m", e.p("name", str_(e)))
    def_iface(e, x, "jthrow_m")
    def_iface(e, x, "jpanic_m")
    def_obj(
        e,
        x,
        "jinst",
        "js statement",
        e.rec(e.p("text", str_(e)), e.p("loc", loc_t(e)), e.p("label", e.call(e.mb.types_option(), str_(e)))),
    )
    def_obj(e, x, "jlabel", "js block label", e.rec(e.p("key", e.types_jump_key()), e.p("name", str_(e))))
    def_obj(e, x, "jcode", "js code", e.rec(e.p("insts", _insts_t(e))))
    x.append(e.impl_interface(e.v("jcode"), e.mb.builtin("eval", "code_dyn")))
    method(e, x, "jcode", "insts", e.tup(), _insts_t(e), in_(e, "insts"))
    def_obj(
        e,
        x,
        "jval",
        "js value",
        e.rec(e.p("ty", ty(e)), e.p("expr", str_(e)), e.p("temp", bool_t(e)), e.p("place", bool_t(e))),
    )
    x.append(
        e.impl_interface(
            e.v("jval"),
            e.fld(e.v("values"), "retag"),
            e.p("retag", _jval(e, e.v("arg"), in_(e, "expr"), in_(e, "temp"), in_(e, "place"))),
        )
    )
    def_obj(
        e,
        x,
        "jmod",
        "js module",
        e.rec(
            e.p("n", int_t(e)),
            e.p("xx", e.call(e.mb.types_option(), e.types_expr_context())),
            e.p("funcs", e.list_type(str_(e))),
            e.p("func_frames", e.list_type(int_t(e))),
            e.p("stmts", e.list_type(str_(e))),
            e.p("stmt_frames", e.list_type(int_t(e))),
            e.p("frames", e.fld(e.v("srcmap"), "table_t")),
            e.p("labels", e.list_type(t(e, "jlabel"))),
        ),
    )
    def_obj(e, x, "jtarget", "js target", e.rec(e.p("mod", _jmod_t(e))))
    def_obj(e, x, "jbinding", "js binding", e.rec(e.p("name", str_(e)), e.p("ty", ty(e))))
    for obj, desc in [
        ("jt_number", "js number type"),
        ("jt_bigint", "js bigint type"),
        ("jt_bool", "js bool type"),
        ("jt_string", "js string type"),
        ("jt_null", "js null type"),
        ("jt_undefined", "js undefined type"),
        ("jt_void", "js void type"),
    ]:
        def_obj(e, x, obj, desc, e.tup())
    for obj, desc in [("jt_fn", "js function type"), ("jt_ctor", "js constructor type")]:
        def_obj(
            e,
            x,
            obj,
            desc,
            e.rec(e.p("params", e.list_type(ty(e))), e.p("ret", ty(e)), e.p("throws", e.call(e.mb.types_option(), ty(e)))),
        )
    def_obj(e, x, "jt_slot", "js slot type", e.rec(e.p("name", str_(e)), e.p("base", ty(e))))
    def_obj(e, x, "jglobal", "js global type", e.rec(e.p("ty", ty(e))))
    def_obj(e, x, "jt_array", "js array type", e.rec(e.p("elem", ty(e))))
    def_obj(e, x, "jt_method", "js method type", e.rec(e.p("name", str_(e)), e.p("sig", ty(e))))
    def_obj(
        e,
        x,
        "jt_obj",
        "js object type",
        e.rec(
            e.p("name", str_(e)),
            e.p("fields", _members_t(e)),
            e.p("methods", _members_t(e)),
            e.p("artifact_id", _artifact_id_opt_t(e)),
        ),
    )
    def_obj(e, x, "jobj_exporter", "js object type exporter", e.tup())
    def_obj(e, x, "jt_union", "js union type", e.rec(e.p("variants", _members_t(e))))
    def_obj(e, x, "jconv", "js conversion", e.rec(e.p("js", str_(e)), e.p("to", ty(e))))
    def_obj(e, x, "jthrow", "js throw", e.tup())
    def_obj(e, x, "jpanic", "js panic", e.tup())
    tm.def_empty_binding(e, x, "jebinding", "js empty value binding")
    def_obj(e, x, "jgfn_t", "js definition function", e.rec(e.p("kind", int_t(e))))

    _fn_def(e, x, "h_insts", code_t(e), _insts_t(e))
    _fn_def(e, x, "h_code", _insts_t(e), code_t(e))
    _fn_def(e, x, "h_resolve", _insts_t(e), _insts_t(e))
    x.append(e.let("h_append_b", e.def_func(e.v("d"), "js.h_append")))
    x.append(e.let("h_append", e.fld(e.v("h_append_b"), "func")))
    e.fn_sigs["h_append"] = [
        e.rec(e.p("out", _insts_t(e)), e.p("code", code_t(e))),
        e.option_type_none(),
        e.option_type_none(),
    ]
    _fn_def(e, x, "h_is_js", e.rec(e.p("xx", xx_t(e)), e.p("cv", cve_t(e))), e.mb.types_bool())
    _fn_def(
        e,
        x,
        "h_args",
        e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("cv", cve_t(e)), e.p("params", e.list_type(ty(e)))),
        e.mb.call(e.mb.types_eresult(), _args_t(e)),
    )
    _fn_def(e, x, "h_const_str", e.rec(e.p("xx", xx_t(e)), e.p("cv", cve_t(e))), str_(e))
    _fn_def(e, x, "h_key_str", e.rec(e.p("xx", xx_t(e)), e.p("cv", cve_t(e))), str_(e))
    _fn_def(e, x, "h_gref", cve_t(e), str_(e))
    _fn_def(e, x, "h_str_lit", str_(e), str_(e))

    fn_impl(
        e,
        x,
        "h_insts",
        body(
            e,
            e.ret(
                e.match_of(
                    e.v("arg"),
                    "c",
                    None,
                    e.p("none", _insts_new(e)),
                    e.p(
                        "target",
                        e.match_of(
                            e.call_m(e.v("c"), "cast", lt(e, "jcode")),
                            "r",
                            None,
                            e.p("ok", e.call_m(e.v("r"), "insts", e.tup())),
                            e.p("errs", e.mb.panic(e.s("js: code belongs to another target"))),
                        ),
                    ),
                )
            ),
        ),
    )
    fn_impl(e, x, "h_code", body(e, e.ret(e.mb.as_(mk_arg(e, "jcode", e.rec(e.p("insts", e.v("arg")))), code_t(e)))))
    fn_impl(e, x, "h_append", body(e, e.foreach(hf(e, "h_insts", a(e, "code")), "i", push(e, a(e, "out"), e.v("i")))))
    # A region's statements laid out: each landing wraps everything before it in the region in its labeled block. The
    # block's returns all come after the region's start, so a block opening there encloses them; blocks landing later
    # enclose the earlier ones.
    fn_impl(
        e,
        x,
        "h_resolve",
        body(
            e,
            _cell(e, "out", _insts_new(e)),
            e.foreach(
                e.v("arg"),
                "i0",
                e.match_of(
                    e.call_m(e.v("i0"), "label", e.tup()),
                    "l",
                    None,
                    e.p(
                        "some",
                        e.seq(
                            e.let("w", _insts_new(e)),
                            push(
                                e, e.v("w"), _inst(e, e.cat(e.v("l"), e.s(": {")), e.call_m(e.v("i0"), "loc", e.tup()))
                            ),
                            e.foreach(
                                _cv(e, "out"),
                                "o",
                                push(
                                    e,
                                    e.v("w"),
                                    _inst(
                                        e,
                                        e.cat(e.s("  "), e.call_m(e.v("o"), "text", e.tup())),
                                        e.call_m(e.v("o"), "loc", e.tup()),
                                    ),
                                ),
                            ),
                            push(
                                e,
                                e.v("w"),
                                _inst(e, e.call_m(e.v("i0"), "text", e.tup()), e.call_m(e.v("i0"), "loc", e.tup())),
                            ),
                            e.mb.set(_cv(e, "out"), e.v("w")),
                        ),
                    ),
                    e.p("none", push(e, _cv(e, "out"), e.v("i0"))),
                ),
            ),
            e.ret(_cv(e, "out")),
        ),
    )
    fn_impl(
        e,
        x,
        "h_is_js",
        body(
            e,
            e.ret(e.if_else(cve_has(e, a(e, "cv")), has(e, xx(e), cve_type(e, a(e, "cv")), "jtype_m"), e.b(False))),
        ),
    )
    args_t = _args_t(e)
    fn_impl(
        e,
        x,
        "h_args",
        body(
            e,
            count_let(e, "np"),
            count_loop(e, "np", a(e, "params")),
            e.let("elems", e.list_new(cve_t(e))),
            e.if_else(
                e.eq(e.fld(e.v("np"), "v"), num(e, 1)),
                push(e, e.v("elems"), a(e, "cv")),
                e.seq(
                    e.if_only(
                        e.not_(cve_has(e, a(e, "cv"))),
                        ret_m(e, e.eresult_err(args_t, loc(e), e.s("js: the call argument has no value"))),
                    ),
                    e.let("tk", lookup(e, xx(e), cve_type(e, a(e, "cv")), asp_iface(e, "tuple"))),
                    e.if_only(
                        e.not_(e.fld(e.v("tk"), "is_some")),
                        ret_m(e, e.eresult_err(args_t, loc(e), e.s("js: the call arguments must be a tuple"))),
                    ),
                    e.foreach(
                        bim(
                            e,
                            asp_iface(e, "tuple"),
                            "take_elements",
                            e.fld(e.v("tk"), "value"),
                            e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, a(e, "cv")))),
                        ),
                        "er",
                        e.match_of(
                            e.v("er"),
                            "__r",
                            None,
                            e.p("ok", push(e, e.v("elems"), e.v("__r"))),
                            e.p("errs", ret_m(e, e.eresult_errs(args_t, e.v("__r")))),
                        ),
                    ),
                ),
            ),
            count_let(e, "ne"),
            count_loop(e, "ne", e.v("elems")),
            e.if_only(
                e.not_(e.eq(e.fld(e.v("ne"), "v"), e.fld(e.v("np"), "v"))),
                ret_m(
                    e,
                    e.eresult_err(
                        args_t,
                        loc(e),
                        e.cat(
                            e.s("js: the call takes "),
                            to_str(e, e.fld(e.v("np"), "v")),
                            e.s(" arguments, not "),
                            to_str(e, e.fld(e.v("ne"), "v")),
                        ),
                    ),
                ),
            ),
            e.let("out", _insts_new(e)),
            e.let("exprs", e.list_new(str_(e))),
            e.let("i", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                a(e, "params"),
                "pt",
                e.seq(
                    e.match_of(
                        cast_value(e, xx(e), loc(e), e.v("pt"), e.call_m(e.v("elems"), "get", e.fld(e.v("i"), "v"))),
                        "__r",
                        None,
                        e.p(
                            "ok",
                            e.seq(
                                _append_code(e, e.v("out"), cve_code(e, e.v("__r"))),
                                push(e, e.v("exprs"), _jv_expr(e, e.v("__r"))),
                            ),
                        ),
                        e.p("errs", ret_m(e, e.eresult_errs(args_t, e.v("__r")))),
                    ),
                    e.incr(e.fld(e.v("i"), "v")),
                ),
            ),
            e.ret(e.eresult_ok(args_t, e.rec(e.p("code", _code_of(e, e.v("out"))), e.p("exprs", e.v("exprs"))))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_const_str",
        body(
            e,
            e.let("sk", lookup(e, xx(e), cve_type(e, a(e, "cv")), e.mb.eval_aspect_string_const())),
            e.if_only(e.not_(e.fld(e.v("sk"), "is_some")), e.mb.panic(e.s("js: expected a constant string"))),
            e.ret(bim(e, e.mb.eval_aspect_string_const(), "get", e.fld(e.v("sk"), "value"), cve_value(e, a(e, "cv")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_key_str",
        body(
            e,
            e.ret(
                e.call(
                    e.eval_builtin("constkey_to_str"),
                    e.call(
                        e.eval_builtin("extract_constkey"),
                        e.rec(e.p("xx", xx(e)), e.p("value", cve_value(e, a(e, "cv")))),
                    ),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_gref",
        body(
            e,
            e.ret(
                e.call(
                    e.mb.must_reinterpret(),
                    e.tup(
                        e.fld(e.call(e.mb.must_reinterpret(), e.tup(cve_value(e, e.v("arg")), voc_t(e))), "data"),
                        str_(e),
                    ),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_str_lit",
        body(
            e,
            e.let("table", escape_table),
            e.let("out", e.list_new(e.mb.types_byte())),
            _push_utf8(e, e.v("out"), e.s('"')),
            e.foreach(
                e.call(e.mb.eval_str_utf8(), e.v("arg")),
                "b",
                e.seq(
                    e.let("esc", e.call_m(e.v("table"), "get", to_str(e, e.mb.as_(e.v("b"), int_t(e))))),
                    e.if_else(
                        e.eq(e.v("esc"), e.s("")), push(e, e.v("out"), e.v("b")), _push_utf8(e, e.v("out"), e.v("esc"))
                    ),
                ),
            ),
            _push_utf8(e, e.v("out"), e.s('"')),
            e.ret(
                e.match_of(
                    e.call(e.eval_builtin("str_from_utf8"), e.v("out")),
                    "__s",
                    None,
                    e.p("some", e.v("__s")),
                    e.p("none", e.mb.panic(e.s("js: string literal is not valid UTF-8"))),
                )
            ),
        ),
    )

    accessor(e, x, "jinst", "text", str_(e))
    accessor(e, x, "jinst", "loc", loc_t(e))
    accessor(e, x, "jinst", "label", e.call(e.mb.types_option(), str_(e)))
    accessor(e, x, "jlabel", "key", e.types_jump_key())
    accessor(e, x, "jlabel", "name", str_(e))
    accessor(e, x, "jval", "expr", str_(e))
    accessor(e, x, "jval", "ty", ty(e))
    accessor(e, x, "jval", "temp", bool_t(e))
    accessor(e, x, "jval", "place", bool_t(e))
    x.append(
        e.impl_interface(
            e.v("jval"),
            e.mb.eval_value(),
            e.p("type", in_(e, "ty")),
            e.p("artifact_exporter", tm.artifact_exporter_impl(e, "jval")),
        )
    )
    accessor(e, x, "jtarget", "mod", _jmod_t(e))
    accessor(e, x, "jbinding", "name", str_(e))
    for vo in ["jinst", "jlabel", "jmod"]:
        marker_type(e, x, vo, vo, vo + "_m", e.aspect_dispatch(lv(e, vo + "_m_id")))
        x.append(e.impl_interface(e.v(vo), t(e, vo + "_m")))
    x.append(
        e.impl_interface(
            e.v("jbinding"),
            e.mb.eval_binding(),
            e.p("use", cv_of(e, a(e, "code"), _jval(e, in_(e, "ty"), in_(e, "name")))),
            e.p("drop", binding_drop_body(e)),
            e.p("fork", outer(e)),
            e.p("merge", e.eresult_ok(e.mb.eval_binding(), outer(e))),
        )
    )

    method(e, x, "jmod", "xx", e.tup(), e.types_expr_context(), in_(e, "xx", "value"))
    x.append(
        e.method_impl(
            e.v("jmod"),
            "set_xx",
            e.types_expr_context(),
            e.option_type_none(),
            e.stage(e.mb.set(in_(e, "xx"), e.opt_some(e.types_expr_context(), e.v("arg")))),
        )
    )
    method(
        e,
        x,
        "jmod",
        "fresh",
        e.tup(),
        str_(e),
        e.seq(e.let("n", in_(e, "n")), e.incr(in_(e, "n")), e.ret(e.cat(e.s("$"), to_str(e, e.v("n"))))),
    )
    # The label of a block's jump key: minted on the first exit or landing that names it.
    method(
        e,
        x,
        "jmod",
        "label_of",
        e.types_jump_key(),
        str_(e),
        body(
            e,
            e.foreach(
                in_(e, "labels"),
                "l",
                e.if_only(
                    e.eq(e.call_m(e.v("l"), "key", e.tup()), e.v("arg")),
                    ret_m(e, e.call_m(e.v("l"), "name", e.tup())),
                ),
            ),
            e.let("n", in_(e, "n")),
            e.incr(in_(e, "n")),
            e.let("name", e.cat(e.s("$L"), to_str(e, e.v("n")))),
            push(e, in_(e, "labels"), mk(e, "jlabel", e.p("key", e.v("arg")), e.p("name", e.v("name")))),
            e.ret(e.v("name")),
        ),
    )
    # A label no jump key names: a block the target places itself (a try's join).
    method(
        e,
        x,
        "jmod",
        "label_fresh",
        e.tup(),
        str_(e),
        e.seq(e.let("n", in_(e, "n")), e.incr(in_(e, "n")), e.ret(e.cat(e.s("$L"), to_str(e, e.v("n"))))),
    )
    # A module-unique name from a hint: every function the module defines gets one, so two definers with one hint
    # never collide; the module's whole text runs in a function scope, so no name reaches the page.
    method(
        e,
        x,
        "jmod",
        "mint",
        str_(e),
        str_(e),
        e.seq(
            e.let("n", in_(e, "n")),
            e.incr(in_(e, "n")),
            e.ret(e.cat(target_mb.ident_of(e, e.v("arg")), e.s("$"), to_str(e, e.v("n")))),
        ),
    )
    method(
        e,
        x,
        "jmod",
        "lower",
        e.rec(
            e.p("params", _params_t(e)),
            e.p("exc", e.call(e.mb.types_option(), ty(e))),
            e.p("body", e.mb.types_expr()),
        ),
        cve_t(e),
        e.seq(
            e.let("entries", e.map_new(e.mb.types_constkey(), e.mb.eval_binding())),
            e.foreach(
                a(e, "params"),
                "pn",
                e.call_m(
                    e.v("entries"),
                    "put",
                    e.tup(
                        e.fld(e.v("pn"), "name"),
                        mk(e, "jbinding", e.p("name", e.fld(e.v("pn"), "name")), e.p("ty", e.fld(e.v("pn"), "ty"))),
                    ),
                ),
            ),
            e.let("vx", e.call(e.eval_builtin("eval_context"), e.tup())),
            e.let("sc", e.call(e.eval_builtin("scope"), e.rec(e.p("vx", e.v("vx")), e.p("entries", e.v("entries"))))),
            e.let("tgt", mk(e, "jtarget", e.p("mod", outer(e)))),
            e.let(
                "ctx",
                e.call(
                    e.eval_builtin("expr_context"),
                    e.rec(
                        e.p("scope", e.v("sc")),
                        e.p("target", e.mb.as_(e.v("tgt"), e.mb.eval_target())),
                        e.p("vx", e.v("vx")),
                        e.p("exception_type", a(e, "exc")),
                    ),
                ),
            ),
            e.ret(
                must_v(
                    e,
                    TARGET,
                    e.call(e.mb.eval_const_eval_function(), e.rec(e.p("xx", e.v("ctx")), e.p("staged", a(e, "body")))),
                    "compile failed",
                )
            ),
        ),
    )
    method(
        e,
        x,
        "jmod",
        "func",
        e.rec(
            e.p("name", str_(e)), e.p("params", e.list_type(str_(e))), e.p("ty", ty(e)), e.p("body", e.mb.types_expr())
        ),
        str_(e),
        e.seq(
            e.let("fname", e.call_m(outer(e), "mint", a(e, "name"))),
            e.let("floc", e.call(e.eval_builtin("expr_loc"), a(e, "body"))),
            e.let("mxx", in_(e, "xx", "value")),
            e.let("ptys", acc(e, e.v("mxx"), a(e, "ty"), "jfn_m", "params")),
            e.let("ret", acc(e, e.v("mxx"), a(e, "ty"), "jfn_m", "ret")),
            e.let("ps", e.list_new(_param_t(e))),
            e.let("pi", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                a(e, "params"),
                "pn",
                e.seq(
                    push(
                        e,
                        e.v("ps"),
                        e.rec(e.p("name", e.v("pn")), e.p("ty", e.call_m(e.v("ptys"), "get", e.fld(e.v("pi"), "v")))),
                    ),
                    e.incr(e.fld(e.v("pi"), "v")),
                ),
            ),
            e.let(
                "r",
                e.call_m(
                    outer(e),
                    "lower",
                    e.rec(
                        e.p("params", e.v("ps")),
                        e.p("exc", acc(e, e.v("mxx"), a(e, "ty"), "jfn_m", "throws")),
                        e.p("body", a(e, "body")),
                    ),
                ),
            ),
            e.let("out", _insts_new(e)),
            # A result converted to the return type carries the body's code; otherwise the body's code is all.
            e.let("returns", and_b(e, e.not_(cve_ended(e, e.v("r"))), e.not_(has(e, e.v("mxx"), e.v("ret"), "jvoid_m")))),
            e.if_only(e.not_(e.v("returns")), _append_code(e, e.v("out"), cve_code(e, e.v("r")))),
            e.if_only(
                and_b(e, e.not_(cve_ended(e, e.v("r"))), has(e, e.v("mxx"), e.v("ret"), "jvoid_m")),
                e.if_only(
                    cve_has(e, e.v("r")),
                    e.mb.panic(
                        e.cat(
                            e.s("js: compile failed: function "),
                            a(e, "name"),
                            e.s(" returns void but its body yields a value"),
                        )
                    ),
                ),
            ),
            e.if_only(
                e.v("returns"),
                e.match_of(
                    cast_value(e, e.v("mxx"), e.v("floc"), e.v("ret"), e.v("r")),
                    "__r",
                    None,
                    e.p(
                        "ok",
                        e.seq(
                            _append_code(e, e.v("out"), cve_code(e, e.v("__r"))),
                            push(
                                e,
                                e.v("out"),
                                _inst(e, e.cat(e.s("return "), _jv_expr(e, e.v("__r")), e.s(";")), e.v("floc")),
                            ),
                        ),
                    ),
                    e.p("errs", panic_errs(e, "js", "compile failed: function result", e.v("__r"))),
                ),
            ),
            e.let("ff", _frame(e, e.v("floc"))),
            push(
                e,
                in_(e, "funcs"),
                e.cat(e.s("function "), e.v("fname"), e.s("("), e.join(a(e, "params"), ", "), e.s(") {")),
            ),
            push(e, in_(e, "func_frames"), e.v("ff")),
            _lines(e, e.v("out"), in_(e, "funcs"), in_(e, "func_frames"), "  "),
            push(e, in_(e, "funcs"), e.s("}")),
            push(e, in_(e, "func_frames"), e.v("ff")),
            e.ret(e.v("fname")),
        ),
    )
    method(
        e,
        x,
        "jmod",
        "func_text",
        e.rec(e.p("name", str_(e)), e.p("params", e.list_type(str_(e))), e.p("lines", e.list_type(str_(e)))),
        str_(e),
        e.seq(
            e.let("fname", e.call_m(outer(e), "mint", a(e, "name"))),
            push(
                e,
                in_(e, "funcs"),
                e.cat(e.s("function "), e.v("fname"), e.s("("), e.join(a(e, "params"), ", "), e.s(") {")),
            ),
            push(e, in_(e, "func_frames"), _no_frame(e)),
            e.foreach(
                a(e, "lines"),
                "l",
                e.seq(
                    push(e, in_(e, "funcs"), e.cat(e.s("  "), e.v("l"))),
                    push(e, in_(e, "func_frames"), _no_frame(e)),
                ),
            ),
            push(e, in_(e, "funcs"), e.s("}")),
            push(e, in_(e, "func_frames"), _no_frame(e)),
            e.ret(e.v("fname")),
        ),
    )
    method(
        e,
        x,
        "jmod",
        "declare",
        str_(e),
        str_(e),
        # A variable keeps its name: the module's text helpers (`func_text` lines) refer to variables by name, and
        # a let-bound variable's minted name cannot reach text at the staged level. The module's function scope keeps
        # the name from the page.
        e.seq(
            push(e, in_(e, "stmts"), e.cat(e.s("let "), e.v("arg"), e.s(";"))),
            push(e, in_(e, "stmt_frames"), _no_frame(e)),
            e.ret(e.v("arg")),
        ),
    )
    x.append(
        e.method_impl(
            e.v("jmod"),
            "assign_index",
            e.rec(e.p("target", str_(e)), e.p("key", str_(e)), e.p("value", str_(e))),
            e.option_type_none(),
            e.stage(
                e.seq(
                    push(
                        e,
                        in_(e, "stmts"),
                        e.cat(
                            a(e, "target"),
                            e.s("["),
                            hf(e, "h_str_lit", a(e, "key")),
                            e.s("] = "),
                            a(e, "value"),
                            e.s(";"),
                        ),
                    ),
                    push(e, in_(e, "stmt_frames"), _no_frame(e)),
                )
            ),
        )
    )
    x.append(
        e.method_impl(
            e.v("jmod"),
            "run",
            e.mb.types_expr(),
            e.option_type_none(),
            e.stage(
                e.seq(
                    e.let(
                        "r",
                        e.call_m(
                            outer(e),
                            "lower",
                            e.rec(
                                e.p("params", e.list_new(_param_t(e))),
                                e.p("exc", e.opt_none(ty(e))),
                                e.p("body", e.v("arg")),
                            ),
                        ),
                    ),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("r"))),
                    _lines(e, e.v("out"), in_(e, "stmts"), in_(e, "stmt_frames"), ""),
                )
            ),
        )
    )
    method(
        e,
        x,
        "jmod",
        "render",
        e.rec(e.p("frames", str_(e))),
        _render_t(e),
        e.seq(
            e.let("all", e.list_new(str_(e))),
            e.let("fr", e.list_new(int_t(e))),
            push(e, e.v("all"), e.s('"use strict";')),
            push(e, e.v("fr"), _no_frame(e)),
            push(e, e.v("all"), e.s("(() => {")),
            push(e, e.v("fr"), _no_frame(e)),
            # A panic's error: guarded regions rethrow it, so no catch takes it.
            push(e, e.v("all"), e.s("class Panic$ extends Error {}")),
            push(e, e.v("fr"), _no_frame(e)),
            e.foreach(in_(e, "funcs"), "f", push(e, e.v("all"), e.v("f"))),
            e.foreach(in_(e, "func_frames"), "f", push(e, e.v("fr"), e.v("f"))),
            e.foreach(in_(e, "stmts"), "s", push(e, e.v("all"), e.v("s"))),
            e.foreach(in_(e, "stmt_frames"), "s", push(e, e.v("fr"), e.v("s"))),
            push(e, e.v("all"), e.s("})();")),
            push(e, e.v("fr"), _no_frame(e)),
            # Source map v3 over one source, the sidecar: every line with a frame is one segment at column 0 whose
            # original line is the frame (the fields are deltas from the previous segment; only the line moves).
            e.let("segs", e.list_new(str_(e))),
            _cell(e, "prev", e.int_of(0)),
            e.foreach(
                e.v("fr"),
                "f",
                e.if_else(
                    e.mb.operator_lt(e.v("f"), e.int_of(0)),
                    push(e, e.v("segs"), e.dstr("")),
                    e.seq(
                        push(
                            e,
                            e.v("segs"),
                            e.cat(
                                e.s("AA"),
                                e.call_m(outer(e), "vlq", e.mb.operator_sub(e.v("f"), _cv(e, "prev"))),
                                e.s("A"),
                            ),
                        ),
                        e.mb.set(_cv(e, "prev"), e.v("f")),
                    ),
                ),
            ),
            e.ret(
                e.rec(
                    e.p("js", e.cat(e.join(e.v("all"), "\n"), e.s("\n"))),
                    e.p(
                        "map",
                        e.cat(
                            e.s('{"version":3,"sources":["'),
                            a(e, "frames"),
                            e.s('"],"names":[],"mappings":"'),
                            e.join(e.v("segs"), ";"),
                            e.s('"}\n'),
                        ),
                    ),
                    e.p("frames", e.call_m(in_(e, "frames"), "render", e.tup())),
                )
            ),
        ),
    )
    method(
        e,
        x,
        "jmod",
        "vlq",
        int_t(e),
        str_(e),
        e.seq(
            e.let("b64", e.list_new(str_(e), *[e.s(c) for c in VLQ_ALPHABET])),
            _cell(
                e,
                "v",
                e.if_else(
                    e.mb.operator_lt(e.v("arg"), e.int_of(0)),
                    e.mb.operator_or(e.mb.operator_shl(e.mb.operator_neg(e.v("arg")), e.int_of(1)), e.int_of(1)),
                    e.mb.operator_shl(e.v("arg"), e.int_of(1)),
                ),
            ),
            _cell(e, "out", e.dstr("")),
            e.mb.labeled(
                "digits",
                e.mb.loop(
                    e.seq(
                        e.let("digit", e.mb.operator_and(_cv(e, "v"), e.int_of(31))),
                        e.mb.set(_cv(e, "v"), e.mb.operator_ushr(_cv(e, "v"), e.int_of(5))),
                        e.let(
                            "d",
                            e.if_else(
                                e.mb.operator_gt(_cv(e, "v"), e.int_of(0)),
                                e.mb.operator_or(e.v("digit"), e.int_of(32)),
                                e.v("digit"),
                            ),
                        ),
                        e.mb.set(_cv(e, "out"), e.cat(_cv(e, "out"), e.call_m(e.v("b64"), "get", e.v("d")))),
                        e.if_only(e.eq(_cv(e, "v"), e.int_of(0)), e.mb.return_label("digits")),
                    )
                ),
            ),
            e.ret(_cv(e, "out")),
        ),
    )

    x.append(
        e.impl_interface(
            e.v("jtarget"),
            e.mb.eval_target(),
            *_exc_hooks(e),
            e.p(
                "seq",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    e.let("st", e.rec(e.p("any", e.int_of(0)))),
                    e.foreach(
                        a(e, "entries"),
                        "en",
                        e.seq(
                            _append_code(e, e.v("out"), e.v("en")),
                            e.if_only(is_target_code(e, e.v("en")), e.mb.set(e.fld(e.v("st"), "any"), num(e, 1))),
                        ),
                    ),
                    e.ret(
                        e.eresult_ok(
                            code_t(e),
                            e.if_else(
                                e.eq(e.fld(e.v("st"), "any"), num(e, 1)), _code_of(e, e.v("out")), code_none(e, loc(e))
                            ),
                        )
                    ),
                ),
            ),
            e.p(
                "land",
                e.eresult_ok(
                    cve_t(e),
                    cv_no(
                        e,
                        _code_of(
                            e,
                            e.list_new(
                                lt(e, "jinst"),
                                _label_inst(e, e.call_m(in_(e, "mod"), "label_of", a(e, "dest")), loc(e)),
                            ),
                        ),
                    ),
                ),
            ),
            e.p("value_is_runtime", e.mb.bool(False)),
            structural_exits(e)[0],
            structural_exits(e)[1],
            # A carried value already sits in the slot its return stored it in.
            e.p(
                "exit",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), a(e, "value", "code")),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            e.cat(e.s("break "), e.call_m(in_(e, "mod"), "label_of", a(e, "dest")), e.s(";")),
                            loc(e),
                        ),
                    ),
                    e.ret(e.eresult_ok(code_t(e), _code_of(e, e.v("out")))),
                ),
            ),
            e.p("drop", target_drop_body(e)),
            # A runtime value goes into a fresh slot; the block's later returns convert into the first one's.
            e.p(
                "return",
                body(
                    e,
                    e.if_only(e.not_(_is_js(e, xx(e), a(e, "cv"))), ret_m(e, a(e, "cv"))),
                    # A stand-in (a slot, a global) answers `base` with the type it holds.
                    e.let("base", acc(e, xx(e), cve_type(e, a(e, "cv")), "jtype_m", "base")),
                    e.let(
                        "v",
                        e.match_of(
                            cast_value(e, xx(e), loc(e), e.v("base"), a(e, "cv")),
                            "__r",
                            None,
                            e.p("ok", e.v("__r")),
                            e.p("errs", panic_errs(e, "js target", "return value", e.v("__r"))),
                        ),
                    ),
                    e.let("r", _fresh(e, in_(e, "mod"))),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                    push(
                        e,
                        e.v("out"),
                        _inst(e, e.cat(e.s("var "), e.v("r"), e.s(" = "), _jv_expr(e, e.v("v")), e.s(";")), loc(e)),
                    ),
                    e.ret(
                        cv_of(
                            e,
                            _code_of(e, e.v("out")),
                            _jval(e, mk(e, "jt_slot", e.p("name", e.v("r")), e.p("base", e.v("base"))), e.v("r")),
                        )
                    ),
                ),
            ),
            e.p("stage", err_cve(e, loc(e), "js target: nested staging is not supported")),
            e.p("if", _if_hook(e)),
            e.p(
                "loop",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    push(e, e.v("out"), _inst(e, e.s("while (true) {"), loc(e))),
                    _push_indented(e, hf(e, "h_insts", cve_code(e, a(e, "body"))), e.dstr(""), "  "),
                    push(e, e.v("out"), _inst(e, e.s("}"), loc(e))),
                    e.ret(ok_cve(e, e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("out"))))),
                ),
            ),
            e.p("match", _match_hook(e)),
        )
    )

    _num_types(e, x)
    _scalar_types(e, x)
    _callable_type(e, x, "jt_fn", "js function", "jfn_m", False)
    _callable_type(e, x, "jt_ctor", "js constructor", "jctor_m", True)
    _slot_type(e, x)
    _global_type(e, x)
    _array_type(e, x)
    _method_type(e, x)
    _object_type(e, x)
    _union_type(e, x)
    _raise_types(e, x)

    self_type(
        e,
        x,
        "jgfn_t",
        e.cat(e.s("js definition function "), to_str(e, in_(e, "kind"))),
        rt_dispatch(e, lt(e, "jmod"), e.aspect_dispatch(lv(e, "jgfn_m_id"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.if_only(e.not_(has(e, xx(e), a(e, "other"), "jgfn_m")), ret_m(e, dfalse(e))),
            e.ret(e.eq(in_(e, "kind"), acc(e, xx(e), a(e, "other"), "jgfn_m", "kind"))),
        ),
    )
    x.append(e.impl_interface(e.v("jgfn_t"), t(e, "jgfn_m"), e.p("kind", in_(e, "kind"))))
    rt_lift_impl(e, x, "jgfn_t")
    rt_bind_impl(e, x, "jgfn_t", lt(e, "jmod"))
    rt_use_impl(e, x, "jgfn_t")
    target_mb.method(
        e,
        x,
        "jgfn_t",
        "call",
        e.rec(e.p("xx", e.types_expr_context()), e.p("loc", loc_t(e)), e.p("argument", cve_t(e))),
        e.mb.call(e.mb.types_eresult(), cve_t(e)),
        body(
            e,
            e.let("argv", a(e, "argument")),
            e.if_only(
                e.not_(cve_has(e, e.v("argv"))),
                ret_m(e, err_cve(e, loc(e), "js definition argument has no value")),
            ),
            e.let("rk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "record"))),
            e.if_only(
                e.not_(e.fld(e.v("rk"), "is_some")),
                ret_m(e, err_cve(e, loc(e), "js definition argument must be a record")),
            ),
            e.let(
                "fields",
                bim(
                    e,
                    asp_iface(e, "record"),
                    "take_fields",
                    e.fld(e.v("rk"), "value"),
                    e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, e.v("argv")))),
                ),
            ),
            # `union{k: T, ...}`: the record's fields are the members.
            e.if_only(
                _jgfn_is(e, "union"),
                e.seq(
                    e.let("vs", e.list_new(_member_t(e))),
                    e.let("tags", e.list_new(str_(e))),
                    e.foreach(
                        bim0(e, asp_iface(e, "record"), "field_types", e.fld(e.v("rk"), "value")),
                        "en",
                        e.seq(
                            e.let("vk", key_str(e, e.fld(e.v("en"), "key"))),
                            e.let("vcv", _jgfn_field(e, e.v("vk"))),
                            *tm.const_type_arg(e, "js union", e.v("vcv"), "vt"),
                            e.if_only(
                                or_b(
                                    e,
                                    e.not_(has(e, xx(e), e.v("vt"), "jtype_m")),
                                    or_b(e, has(e, xx(e), e.v("vt"), "junion_m"), has(e, xx(e), e.v("vt"), "jmethod_m")),
                                ),
                                ret_m(
                                    e,
                                    err_cve(
                                        e,
                                        loc(e),
                                        e.cat(e.s("js union members must be plain js types, not "), ty_desc(e, e.v("vt"))),
                                    ),
                                ),
                            ),
                            e.let("vtag", _tag(e, xx(e), e.v("vt"))),
                            e.foreach(
                                e.v("tags"),
                                "t0",
                                e.if_only(
                                    e.eq(e.v("t0"), e.v("vtag")),
                                    ret_m(
                                        e,
                                        err_cve(
                                            e,
                                            loc(e),
                                            e.cat(
                                                e.s("js union members cannot be told apart: two have the runtime tag "),
                                                e.v("vtag"),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                            push(e, e.v("tags"), e.v("vtag")),
                            push(e, e.v("vs"), e.rec(e.p("name", e.v("vk")), e.p("ty", e.v("vt")))),
                        ),
                    ),
                    e.let("ut", mk(e, "jt_union", e.p("variants", e.v("vs")))),
                    ret_m(e, ok_cve(e, _jgfn_staged(e, e.lower(e.mb.as_(e.v("ut"), ty(e)))))),
                ),
            ),
            # `fn` and `ctor` take an optional `throws`.
            e.let("hast", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                bim0(e, asp_iface(e, "record"), "field_types", e.fld(e.v("rk"), "value")),
                "en0",
                e.if_only(
                    e.eq(key_str(e, e.fld(e.v("en0"), "key")), e.s("throws")),
                    e.mb.set(e.fld(e.v("hast"), "v"), num(e, 1)),
                ),
            ),
            e.let(
                "want",
                e.if_else(
                    _jgfn_is(e, "global_fn"),
                    e.list_new(str_(e), e.s("name"), e.s("ty")),
                    e.if_else(
                        _jgfn_is(e, "var_fn"),
                        e.list_new(str_(e), e.s("mod"), e.s("name"), e.s("ty")),
                        e.if_else(
                            or_b(e, _jgfn_is(e, "fn"), _jgfn_is(e, "ctor")),
                            e.if_else(
                                e.eq(e.fld(e.v("hast"), "v"), num(e, 1)),
                                e.list_new(str_(e), e.s("params"), e.s("ret"), e.s("throws")),
                                e.list_new(str_(e), e.s("params"), e.s("ret")),
                            ),
                            e.if_else(
                                _jgfn_is(e, "array"),
                                e.list_new(str_(e), e.s("elem")),
                                e.if_else(
                                    _jgfn_is(e, "object"),
                                    e.list_new(str_(e), e.s("name")),
                                    e.if_else(
                                        _jgfn_is(e, "members"),
                                        e.list_new(str_(e), e.s("object"), e.s("fields"), e.s("methods")),
                                        e.list_new(
                                            str_(e), e.s("mod"), e.s("name"), e.s("params"), e.s("ty"), e.s("body")
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            e.let("kc", e.rec(e.p("n", e.int_of(0)), e.p("bad", e.dstr("")))),
            e.foreach(
                bim0(e, asp_iface(e, "record"), "field_types", e.fld(e.v("rk"), "value")),
                "en",
                e.seq(
                    e.incr(e.fld(e.v("kc"), "n")),
                    e.let("ks", key_str(e, e.fld(e.v("en"), "key"))),
                    e.let("hit", e.rec(e.p("v", e.int_of(0)))),
                    e.foreach(
                        e.v("want"),
                        "w",
                        e.if_only(e.eq(e.v("w"), e.v("ks")), e.mb.set(e.fld(e.v("hit"), "v"), num(e, 1))),
                    ),
                    e.if_only(e.eq(e.fld(e.v("hit"), "v"), num(e, 0)), e.mb.set(e.fld(e.v("kc"), "bad"), e.v("ks"))),
                ),
            ),
            count_let(e, "wn"),
            count_loop(e, "wn", e.v("want")),
            e.if_only(
                or_b(
                    e,
                    e.not_(e.eq(e.fld(e.v("kc"), "bad"), e.s(""))),
                    e.not_(e.eq(e.fld(e.v("kc"), "n"), e.fld(e.v("wn"), "v"))),
                ),
                ret_m(
                    e,
                    err_cve(
                        e, loc(e), e.cat(e.s("js definition takes exactly the fields "), e.join(e.v("want"), ", "))
                    ),
                ),
            ),
            # `fn{params: (T, ...), ret}` and `ctor{params, ret}`: a function or constructor type, a constant.
            e.if_only(
                or_b(e, _jgfn_is(e, "fn"), _jgfn_is(e, "ctor")),
                e.seq(
                    e.let("ptys", e.list_new(ty(e))),
                    e.let("pcv", _jgfn_field(e, "params")),
                    e.let("ptk", lookup(e, xx(e), cve_type(e, e.v("pcv")), asp_iface(e, "tuple"))),
                    e.if_only(
                        e.not_(e.fld(e.v("ptk"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "js fn/ctor params must be a tuple of types")),
                    ),
                    e.foreach(
                        bim(
                            e,
                            asp_iface(e, "tuple"),
                            "take_elements",
                            e.fld(e.v("ptk"), "value"),
                            e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, e.v("pcv")))),
                        ),
                        "er",
                        e.seq(
                            e.let("ecv", unwrap_cve_m(e, e.v("er"))),
                            *tm.const_type_arg(e, "js fn/ctor", e.v("ecv"), "pt"),
                            e.if_only(
                                e.not_(has(e, xx(e), e.v("pt"), "jtype_m")),
                                ret_m(
                                    e,
                                    err_cve(
                                        e,
                                        loc(e),
                                        e.cat(e.s("js fn/ctor parameters must be js types, not "), ty_desc(e, e.v("pt"))),
                                    ),
                                ),
                            ),
                            push(e, e.v("ptys"), e.v("pt")),
                        ),
                    ),
                    e.let("rcv", _jgfn_field(e, "ret")),
                    *tm.const_type_arg(e, "js fn/ctor", e.v("rcv"), "rt"),
                    e.if_only(
                        e.not_(
                            or_b(
                                e,
                                has(e, xx(e), e.v("rt"), "jtype_m"),
                                and_b(e, _jgfn_is(e, "fn"), has(e, xx(e), e.v("rt"), "jvoid_m")),
                            )
                        ),
                        ret_m(
                            e,
                            err_cve(
                                e,
                                loc(e),
                                e.cat(e.s("js fn/ctor ret must be a js type (or void for fn), not "), ty_desc(e, e.v("rt"))),
                            ),
                        ),
                    ),
                    e.let("thrs", e.list_new(ty(e))),
                    e.if_only(
                        e.eq(e.fld(e.v("hast"), "v"), num(e, 1)),
                        e.seq(
                            e.let("tcv", _jgfn_field(e, "throws")),
                            *tm.const_type_arg(e, "js fn/ctor", e.v("tcv"), "tt"),
                            e.if_only(
                                e.not_(has(e, xx(e), e.v("tt"), "jtype_m")),
                                ret_m(
                                    e,
                                    err_cve(
                                        e,
                                        loc(e),
                                        e.cat(e.s("js fn/ctor throws must be a js type, not "), ty_desc(e, e.v("tt"))),
                                    ),
                                ),
                            ),
                            push(e, e.v("thrs"), e.v("tt")),
                        ),
                    ),
                    e.let(
                        "thr",
                        e.if_else(
                            e.eq(e.fld(e.v("hast"), "v"), num(e, 1)),
                            e.opt_some(ty(e), e.call_m(e.v("thrs"), "get", e.int_of(0))),
                            e.opt_none(ty(e)),
                        ),
                    ),
                    e.let(
                        "sig",
                        e.if_else(
                            _jgfn_is(e, "fn"),
                            e.mb.as_(
                                mk(e, "jt_fn", e.p("params", e.v("ptys")), e.p("ret", e.v("rt")), e.p("throws", e.v("thr"))),
                                ty(e),
                            ),
                            e.mb.as_(
                                mk(e, "jt_ctor", e.p("params", e.v("ptys")), e.p("ret", e.v("rt")), e.p("throws", e.v("thr"))),
                                ty(e),
                            ),
                        ),
                    ),
                    ret_m(e, ok_cve(e, _jgfn_staged(e, e.lower(e.v("sig"))))),
                ),
            ),
            e.if_only(
                _jgfn_is(e, "array"),
                e.seq(
                    e.let("ecv", _jgfn_field(e, "elem")),
                    *tm.const_type_arg(e, "js array", e.v("ecv"), "el"),
                    e.if_only(
                        e.not_(has(e, xx(e), e.v("el"), "jtype_m")),
                        ret_m(e, err_cve(e, loc(e), e.cat(e.s("js array elem must be a js type, not "), ty_desc(e, e.v("el"))))),
                    ),
                    e.let("at", mk(e, "jt_array", e.p("elem", e.v("el")))),
                    ret_m(e, ok_cve(e, _jgfn_staged(e, e.lower(e.mb.as_(e.v("at"), ty(e)))))),
                ),
            ),
            # `members{object, fields: {k: T}, methods: {k: fn}}` attaches members to a declared object type.
            e.if_only(
                _jgfn_is(e, "members"),
                e.seq(
                    e.let("ocv", _jgfn_field(e, "object")),
                    *tm.const_type_arg(e, "js members", e.v("ocv"), "ot"),
                    e.if_only(
                        e.not_(has(e, xx(e), e.v("ot"), "jobj_m")),
                        ret_m(e, err_cve(e, loc(e), e.cat(e.s("js members object must be a js.object type, not "), ty_desc(e, e.v("ot"))))),
                    ),
                    e.let("oo", reinterpret(e, e.v("ot"), "jt_obj")),
                    *[
                        e.seq(
                            e.let(kind + "_cv", _jgfn_field(e, kind)),
                            e.let(kind + "_rk", lookup(e, xx(e), cve_type(e, e.v(kind + "_cv")), asp_iface(e, "record"))),
                            e.if_only(
                                e.not_(e.fld(e.v(kind + "_rk"), "is_some")),
                                ret_m(e, err_cve(e, loc(e), "js members " + kind + " must be a record of types")),
                            ),
                            e.let(
                                kind + "_f",
                                bim(
                                    e,
                                    asp_iface(e, "record"),
                                    "take_fields",
                                    e.fld(e.v(kind + "_rk"), "value"),
                                    e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, e.v(kind + "_cv")))),
                                ),
                            ),
                            e.foreach(
                                bim0(e, asp_iface(e, "record"), "field_types", e.fld(e.v(kind + "_rk"), "value")),
                                "en",
                                e.seq(
                                    e.let("mk", key_str(e, e.fld(e.v("en"), "key"))),
                                    e.let("mcv", unwrap_cve_m(e, e.call_m(e.v(kind + "_f"), "get", e.v("mk")))),
                                    *tm.const_type_arg(e, "js members", e.v("mcv"), "mt"),
                                    e.if_only(
                                        e.not_(has(e, xx(e), e.v("mt"), "jfn_m" if kind == "methods" else "jtype_m")),
                                        ret_m(
                                            e,
                                            err_cve(
                                                e,
                                                loc(e),
                                                e.cat(
                                                    e.s("js members " + kind + " must be " + ("function types" if kind == "methods" else "js types") + ", not "),
                                                    ty_desc(e, e.v("mt")),
                                                ),
                                            ),
                                        ),
                                    ),
                                    e.call_m(e.v("oo"), "add_" + kind, e.rec(e.p("name", e.v("mk")), e.p("ty", e.v("mt")))),
                                ),
                            ),
                        )
                        for kind in ["fields", "methods"]
                    ],
                    ret_m(e, ok_cve(e, cv_no(e, code_none(e, loc(e))))),
                ),
            ),
            e.let("namecv", _jgfn_staged(e, graft(e, _jgfn_field(e, "name")))),
            e.if_only(
                is_runtime(e, e.v("namecv")),
                ret_m(e, err_cve(e, loc(e), "js definition name must be constant")),
            ),
            e.let("name", _const_str(e, e.v("namecv"))),
            e.if_only(
                _jgfn_is(e, "object"),
                e.seq(
                    e.let(
                        "obt",
                        mk(
                            e,
                            "jt_obj",
                            e.p("name", e.v("name")),
                            e.p("fields", e.list_new(_member_t(e))),
                            e.p("methods", e.list_new(_member_t(e))),
                            e.p("artifact_id", e.opt_none(e.mb.builtin("types", "artifact_id_source"))),
                        ),
                    ),
                    ret_m(e, ok_cve(e, _jgfn_staged(e, e.lower(e.mb.as_(e.v("obt"), ty(e)))))),
                ),
            ),
            e.let("tycv", _jgfn_field(e, "ty")),
            *tm.const_type_arg(e, "js definition", e.v("tycv"), "ty"),
            e.if_only(
                e.not_(has(e, xx(e), e.v("ty"), "jtype_m")),
                ret_m(
                    e, err_cve(e, loc(e), e.cat(e.s("js definition ty must be a js type, not "), ty_desc(e, e.v("ty"))))
                ),
            ),
            e.if_only(
                _jgfn_is(e, "global_fn"),
                ret_m(e, tag_value(e, e.v("namecv"), mk(e, "jglobal", e.p("ty", e.v("ty"))))),
            ),
            e.let("modcv", _jgfn_field(e, "mod")),
            e.if_only(
                _jgfn_is(e, "var_fn"),
                e.seq(
                    e.let(
                        "varcv",
                        _jgfn_staged(
                            e,
                            e.call_m(e.call_m(graft(e, e.v("modcv")), "m", e.tup()), "declare", e.lower(e.v("name"))),
                        ),
                    ),
                    ret_m(e, tag_value(e, e.v("varcv"), mk(e, "jglobal", e.p("ty", e.v("ty"))))),
                ),
            ),
            e.if_only(
                e.not_(has(e, xx(e), e.v("ty"), "jfn_m")),
                ret_m(
                    e,
                    err_cve(
                        e, loc(e), e.cat(e.s("js func_fn ty must be a function type, not "), ty_desc(e, e.v("ty")))
                    ),
                ),
            ),
            e.let("pcv", _jgfn_field(e, "params")),
            e.let("ptk", lookup(e, xx(e), cve_type(e, e.v("pcv")), asp_iface(e, "tuple"))),
            e.if_only(
                e.not_(e.fld(e.v("ptk"), "is_some")),
                ret_m(e, err_cve(e, loc(e), "js function params must be a tuple of names")),
            ),
            e.let("names", e.list_new(str_(e))),
            e.foreach(
                bim(
                    e,
                    asp_iface(e, "tuple"),
                    "take_elements",
                    e.fld(e.v("ptk"), "value"),
                    e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, e.v("pcv")))),
                ),
                "er",
                e.seq(
                    e.let("ncv", _jgfn_staged(e, graft(e, unwrap_cve_m(e, e.v("er"))))),
                    e.if_only(
                        is_runtime(e, e.v("ncv")),
                        ret_m(e, err_cve(e, loc(e), "js function parameter names must be constant")),
                    ),
                    push(e, e.v("names"), _const_str(e, e.v("ncv"))),
                ),
            ),
            count_let(e, "nn"),
            count_loop(e, "nn", e.v("names")),
            count_let(e, "nt"),
            count_loop(e, "nt", acc(e, xx(e), e.v("ty"), "jfn_m", "params")),
            e.if_only(
                e.not_(e.eq(e.fld(e.v("nn"), "v"), e.fld(e.v("nt"), "v"))),
                ret_m(e, err_cve(e, loc(e), "js func_fn needs one parameter name per parameter of its type")),
            ),
            e.let("bodycv", _jgfn_field(e, "body")),
            e.let(
                "refcv",
                _jgfn_staged(
                    e,
                    e.call_m(
                        e.call_m(graft(e, e.v("modcv")), "m", e.tup()),
                        "func",
                        e.rec(
                            e.p("name", e.lower(e.v("name"))),
                            e.p("params", e.lower(e.v("names"))),
                            e.p("ty", e.lower(e.v("ty"))),
                            e.p("body", graft(e, e.v("bodycv"))),
                        ),
                    ),
                ),
            ),
            e.ret(tag_value(e, e.v("refcv"), mk(e, "jglobal", e.p("ty", e.v("ty"))))),
        ),
    )

    x.append(e.let("js_b", e.def_func(e.v("d"), "js")))
    x.append(
        e.func_impl(
            e.v("js_b"),
            e.tup(),
            e.option_type_some(t(e, "jmod")),
            e.mb.opt_none_type(),
            e.stage(
                e.seq(
                    e.let(
                        "m",
                        mk(
                            e,
                            "jmod",
                            e.p("n", num(e, 0)),
                            e.p("xx", e.opt_none(e.types_expr_context())),
                            e.p("funcs", e.list_new(str_(e))),
                            e.p("func_frames", e.list_new(int_t(e))),
                            e.p("stmts", e.list_new(str_(e))),
                            e.p("stmt_frames", e.list_new(int_t(e))),
                            e.p("frames", e.call(e.lower(e.fld(e.v("srcmap"), "new")), e.tup())),
                            e.p("labels", e.list_new(lt(e, "jlabel"))),
                        ),
                    ),
                    e.let("tgt", mk(e, "jtarget", e.p("mod", e.v("m")))),
                    e.let("vx", e.call(e.eval_builtin("eval_context"), e.tup())),
                    e.let(
                        "sc",
                        e.call(
                            e.eval_builtin("scope"),
                            e.rec(
                                e.p("vx", e.v("vx")),
                                e.p("entries", e.map_new(e.mb.types_constkey(), e.mb.eval_binding())),
                            ),
                        ),
                    ),
                    e.let(
                        "ctx",
                        e.call(
                            e.eval_builtin("expr_context"),
                            e.rec(
                                e.p("scope", e.v("sc")),
                                e.p("target", e.mb.as_(e.v("tgt"), e.mb.eval_target())),
                                e.p("vx", e.v("vx")),
                                e.p("exception_type", e.mb.opt_none_type()),
                            ),
                        ),
                    ),
                    e.call_m(e.v("m"), "set_xx", e.v("ctx")),
                    e.ret(e.v("m")),
                )
            ),
        )
    )
    x.append(e.finish(e.v("d")))
    defs = []
    defs.append(e.p("new", e.fld(e.v("js_b"), "func")))
    defs.append(e.p("mod_t", t(e, "jmod")))
    for obj in ["jthrow", "jpanic", "jt_number", "jt_bigint", "jt_bool", "jt_string", "jt_null", "jt_undefined", "jt_void", "jgfn_t"]:
        defs.append(e.p(obj + "_new", e.fld(e.v(obj), "new")))
    x.append(e.ret(e.rec(*defs)))

    y = []
    y.append(e.let("k", e.lower(e.mb.seq(x))))
    exported = []
    for name, obj in [
        ("number", "jt_number"),
        ("bigint", "jt_bigint"),
        ("bool", "jt_bool"),
        ("string", "jt_string"),
        ("null", "jt_null"),
        ("undefined", "jt_undefined"),
        ("void", "jt_void"),
        ("throw", "jthrow"),
        ("panic", "jpanic"),
    ]:
        exported.append(name)
        y.append(e.let(name, e.mb.as_(e.call(e.fld(e.v("k"), obj + "_new"), e.tup()), ty(e))))
    for kind in JGFN_KINDS:
        exported.append(kind)
        y.append(
            e.let(kind + "_o", e.call(e.fld(e.v("k"), "jgfn_t_new"), e.rec(e.p("kind", e.int_of(_jgfn_kind(kind))))))
        )
    y.append(e.let("d", e.define()))
    y.append(e.let("gfn_d", e.define()))
    for kind in JGFN_KINDS:
        target_mb.const_fn(
            e,
            y,
            kind + "_b",
            "js." + kind,
            e.call_m(
                e.lower(e.v(kind + "_o")),
                "call",
                e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("argument", a(e, "argument"))),
            ),
            d="gfn_d",
        )
        y.append(e.let(kind, e.fld(e.v(kind + "_b"), "func")))
    y.append(e.finish(e.v("gfn_d")))
    y.append(e.option_type_let())
    y.append(e.let("mod_o", e.def_object(e.v("d"), "js module")))
    y.append(e.object_impl(e.v("mod_o"), e.rec(e.p("m", e.fld(e.v("k"), "mod_t")))))
    y.append(
        e.method_impl(
            e.v("mod_o"),
            "render",
            e.rec(e.p("frames", str_(e))),
            e.option_type_some(_render_t(e)),
            e.stage(e.call_m(in_(e, "m"), "render", e.v("arg"))),
        )
    )
    y.append(
        e.method_impl(e.v("mod_o"), "m", e.tup(), e.option_type_some(e.fld(e.v("k"), "mod_t")), e.stage(in_(e, "m")))
    )
    y.append(
        e.method_impl(
            e.v("mod_o"),
            "run",
            e.mb.types_expr(),
            e.option_type_none(),
            e.stage(e.call_m(in_(e, "m"), "run", e.v("arg"))),
        )
    )
    y.append(
        e.method_impl(
            e.v("mod_o"),
            "assign_index",
            e.rec(e.p("target", str_(e)), e.p("key", str_(e)), e.p("value", str_(e))),
            e.option_type_none(),
            e.stage(e.call_m(in_(e, "m"), "assign_index", e.v("arg"))),
        )
    )
    y.append(
        e.method_impl(
            e.v("mod_o"),
            "func_text",
            e.rec(e.p("name", str_(e)), e.p("params", e.list_type(str_(e))), e.p("lines", e.list_type(str_(e)))),
            e.option_type_some(str_(e)),
            e.stage(e.call_m(in_(e, "m"), "func_text", e.v("arg"))),
        )
    )
    y.append(
        e.method_impl(
            e.v("mod_o"),
            "fresh",
            e.tup(),
            e.option_type_some(str_(e)),
            e.stage(e.call_m(in_(e, "m"), "fresh", e.tup())),
        )
    )
    y.append(e.let("js_b", e.def_func(e.v("d"), "js")))
    y.append(
        e.func_impl(
            e.v("js_b"),
            e.tup(),
            e.option_type_some(e.fld(e.v("mod_o"), "type")),
            e.mb.opt_none_type(),
            e.stage(mk_arg(e, "mod_o", e.rec(e.p("m", e.call(e.fld(e.lower_v("k"), "new"), e.tup()))))),
        )
    )
    y.append(e.finish(e.v("d")))
    ydefs = []
    ydefs.append(e.p("new", e.fld(e.v("js_b"), "func")))
    ydefs.append(e.p("mod_t", e.fld(e.v("mod_o"), "type")))
    for name in exported:
        ydefs.append(e.p(name, e.v(name)))
    y.append(e.ret(e.rec(*ydefs)))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(y))))
    exports = []
    for name in ["new", "mod_t"]:
        exports.append(e.p(name, e.fld(e.v("k"), name)))
    for name in exported:
        exports.append(e.p(name, e.fld(e.v("k"), name)))
    top.append(e.ret(e.rec(*exports)))
    return top
