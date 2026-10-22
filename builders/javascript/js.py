"""js-es2020.atz: JavaScript target (one `any` value type, globals, `new`, definition functions, structured `if`).

Every call, `new` and `if` result lands in a fresh `const` (or `let` for an `if`); a binding of such a value is that
variable itself (no copy), while a binding of any other expression copies it into a fresh `const`. Bindings are
never reassigned. Names: functions and temporaries are minted per module (`hint$n`); `declare`d variables keep
their names for the module's text helpers."""

from .. import target_mb
from ..core import srcmap, values
from .. import target_mb as tm
from ..target_mb import (
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
    errs_t,
    fn_impl,
    fn_throws,
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
    throw_err,
    to_str,
    try_er,
    ty,
    unwrap_cve_m,
    unwrap_cve_t,
    unwrap_m,
    voc_t,
    xx,
    xx_t,
)

TARGET = "js"

JGFN_KINDS = ["global_fn", "func_fn", "new_fn", "var_fn"]


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
    return mk(e, "jinst", e.p("text", text), e.p("loc", loc_))


def _cell(e, name, value):
    return e.let(name, e.rec(e.p("v", value)))


def _cv(e, name):
    return e.fld(e.v(name), "v")


def _jany_t(e):
    return mk_arg(e, "jany", e.tup())


def _jval_new(e, expr):
    return mk(e, "jval", e.p("ty", _jany_t(e)), e.p("expr", expr), e.p("temp", e.b(False)))


def _jval_temp(e, name):
    """A value held in a fresh `const` of its own, which a binding reuses by name instead of copying."""
    return mk(e, "jval", e.p("ty", _jany_t(e)), e.p("expr", name), e.p("temp", e.b(True)))


def _jv_expr(e, cve_tp):
    return e.call_m(reinterpret(e, cve_value(e, cve_tp), "jval"), "expr", e.tup())


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


def _operand(e, xx_, loc_, cv):
    return hf_rec(e, "h_operand", e.p("xx", xx_), e.p("loc", loc_), e.p("cv", cv))


def _is_js(e, xx_, cv):
    return hf_rec(e, "h_is_js", e.p("xx", xx_), e.p("cv", cv))


def _operand_m(e, cv):
    return unwrap_cve_m(e, try_er(e, _operand(e, xx(e), loc(e), cv), cve_t(e)))


def _if_branch_stmts(e, cv_var):
    """Appends a branch's statements to `bo`, assigning its value (if any) to the if's result variable, and tracks
    in `st` whether branches have values and whether any falls through."""
    valued = and_b(e, cve_has(e, e.v(cv_var)), _is_js(e, xx(e), e.v(cv_var)))
    return e.seq(
        e.if_only(
            and_b(e, cve_has(e, e.v(cv_var)), e.not_(_is_js(e, xx(e), e.v(cv_var)))),
            ret_m(e, err_cve(e, loc(e), "if branches must yield js values")),
        ),
        e.if_only(e.not_(valued), _append_code(e, e.v("bo"), cve_code(e, e.v(cv_var)))),
        e.if_only(
            valued,
            e.seq(
                e.mb.set(e.fld(e.v("st"), "has"), num(e, 1)),
                e.let("bv", _operand_m(e, e.v(cv_var))),
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
    """Two spaces per nesting level up to `depth` (bounded by the condition count)."""
    return e.seq(
        e.let("__pre", e.rec(e.p("v", e.dstr("")))),
        e.let("__k", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(
            a(e, "conditions"),
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
    return e.foreach(
        insts,
        "i0",
        push(
            e,
            e.v("out"),
            _inst(e, e.cat(pre, e.s(extra), e.call_m(e.v("i0"), "text", e.tup())), e.call_m(e.v("i0"), "loc", e.tup())),
        ),
    )


def _if_hook(e):
    """A structured `if`: each later condition nests in the previous `else` (its statements run only there); a
    valued `if` declares a result variable assigned in every branch."""
    return body(
        e,
        e.let("mod", _xmod(e)),
        e.let("out", _insts_new(e)),
        e.let(
            "st",
            e.rec(
                e.p("ended", e.int_of(1)),
                e.p("has", e.int_of(0)),
                e.p("novalue", e.int_of(0)),
                e.p("res", _fresh(e, e.v("mod"))),
            ),
        ),
        count_let(e, "nc"),
        count_loop(e, "nc", a(e, "conditions")),
        e.let("ci", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(
            a(e, "conditions"),
            "br",
            e.seq(
                e.let("c", _operand_m(e, e.fld(e.v("br"), "condition"))),
                e.let("pre", _indent(e, e.fld(e.v("ci"), "v"))),
                e.let("cl", _insts_new(e)),
                _append_code(e, e.v("cl"), cve_code(e, e.v("c"))),
                _push_indented(e, e.v("cl"), e.v("pre"), ""),
                push(
                    e, e.v("out"), _inst(e, e.cat(e.v("pre"), e.s("if ("), _jv_expr(e, e.v("c")), e.s(") {")), loc(e))
                ),
                e.let("bo", _insts_new(e)),
                e.let("b", e.fld(e.v("br"), "body")),
                _if_branch_stmts(e, "b"),
                _push_indented(e, e.v("bo"), e.v("pre"), "  "),
                e.incr(e.fld(e.v("ci"), "v")),
                e.if_else(
                    or_b(
                        e,
                        e.mb.operator_lt(e.fld(e.v("ci"), "v"), e.fld(e.v("nc"), "v")),
                        e.fld(a(e, "else"), "is_some"),
                    ),
                    push(e, e.v("out"), _inst(e, e.cat(e.v("pre"), e.s("} else {")), loc(e))),
                    push(e, e.v("out"), _inst(e, e.cat(e.v("pre"), e.s("}")), loc(e))),
                ),
            ),
        ),
        e.if_only(
            e.fld(a(e, "else"), "is_some"),
            e.seq(
                e.let("pre", _indent(e, e.fld(e.v("nc"), "v"))),
                e.let("bo", _insts_new(e)),
                e.let("b", e.fld(a(e, "else"), "value")),
                _if_branch_stmts(e, "b"),
                _push_indented(e, e.v("bo"), e.v("pre"), ""),
                push(
                    e,
                    e.v("out"),
                    _inst(e, e.cat(_indent(e, e.mb.operator_sub(e.fld(e.v("nc"), "v"), num(e, 1))), e.s("}")), loc(e)),
                ),
            ),
        ),
        e.if_only(
            e.not_(e.fld(a(e, "else"), "is_some")),
            e.seq(
                e.mb.set(e.fld(e.v("st"), "ended"), num(e, 0)),
                e.if_only(e.eq(e.fld(e.v("st"), "has"), num(e, 1)), e.mb.set(e.fld(e.v("st"), "novalue"), num(e, 1))),
            ),
        ),
        e.let("depth", e.rec(e.p("v", e.mb.operator_sub(e.fld(e.v("nc"), "v"), num(e, 2))))),
        e.foreach(
            a(e, "conditions"),
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
            ret_m(e, err_cve(e, loc(e), "if: some branches yield a value and some do not")),
        ),
        e.let("all", _insts_new(e)),
        push(e, e.v("all"), _inst(e, e.cat(e.s("let "), e.fld(e.v("st"), "res"), e.s(";")), loc(e))),
        e.foreach(e.v("out"), "i0", push(e, e.v("all"), e.v("i0"))),
        e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("all")), _jval_new(e, e.fld(e.v("st"), "res"))))),
    )


def _const_str(e, cv):
    return hf_rec(e, "h_const_str", e.p("xx", xx(e)), e.p("cv", cv))


def _args_t(e):
    return e.rec(e.p("code", code_t(e)), e.p("exprs", e.list_type(str_(e))))


def _args_of(e):
    return unwrap_m(
        e,
        try_er(e, hf_rec(e, "h_args", e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("cv", a(e, "argument"))), _args_t(e)),
        cve_t(e),
    )


def _jgfn_kind(kind):
    return JGFN_KINDS.index(kind)


def _jgfn_is(e, kind):
    return e.eq(in_(e, "kind"), num(e, _jgfn_kind(kind)))


def _jgfn_staged(e, staged):
    return unwrap_cve_m(e, const_eval_in(e, xx(e), loc(e), e.stage(staged)))


def _jgfn_field(e, key):
    return unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s(key)))


def _push_utf8(e, out, text):
    return e.foreach(e.call(e.mb.eval_str_utf8(), text), "__b", push(e, out, e.v("__b")))


def _lines(e, insts, out, frames_out, indent):
    """Appends the statements' text to `out` (a jmod's line list) and each one's frame to `frames_out`."""
    return e.foreach(
        insts,
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
    def_iface(e, x, "jany_m")
    def_iface(e, x, "jglobal_m")
    def_iface(e, x, "jnew_m")
    def_iface(e, x, "jgfn_m", e.p("kind", int_t(e)))
    def_iface(e, x, "jinst_m")
    def_iface(e, x, "jmod_m")
    def_iface(e, x, "jbinding_m")
    def_obj(e, x, "jinst", "js statement", e.rec(e.p("text", str_(e)), e.p("loc", loc_t(e))))
    def_obj(e, x, "jcode", "js code", e.rec(e.p("insts", _insts_t(e))))
    x.append(e.impl_interface(e.v("jcode"), e.mb.builtin("eval", "code_dyn")))
    method(e, x, "jcode", "insts", e.tup(), _insts_t(e), in_(e, "insts"))
    def_obj(e, x, "jval", "js value", e.rec(e.p("ty", ty(e)), e.p("expr", str_(e)), e.p("temp", bool_t(e))))
    x.append(
        e.impl_interface(
            e.v("jval"),
            e.fld(e.v("values"), "retag"),
            e.p(
                "retag", mk(e, "jval", e.p("ty", e.v("arg")), e.p("expr", in_(e, "expr")), e.p("temp", in_(e, "temp")))
            ),
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
        ),
    )
    def_obj(e, x, "jtarget", "js target", e.rec(e.p("mod", _jmod_t(e))))
    def_obj(e, x, "jbinding", "js binding", e.rec(e.p("name", str_(e))))
    def_obj(e, x, "jany", "js value type", e.tup())
    def_obj(e, x, "jglobal", "js global type", e.tup())
    def_obj(e, x, "jnew", "js new type", e.tup())
    def_obj(e, x, "jgfn_t", "js definition function", e.rec(e.p("kind", int_t(e))))

    _fn_def(e, x, "h_insts", code_t(e), _insts_t(e))
    _fn_def(e, x, "h_code", _insts_t(e), code_t(e))
    x.append(e.let("h_append_b", e.def_func(e.v("d"), "js.h_append")))
    x.append(e.let("h_append", e.fld(e.v("h_append_b"), "func")))
    e.fn_sigs["h_append"] = [
        e.rec(e.p("out", _insts_t(e)), e.p("code", code_t(e))),
        e.option_type_none(),
        e.option_type_none(),
    ]
    _fn_def(e, x, "h_is_js", e.rec(e.p("xx", xx_t(e)), e.p("cv", cve_t(e))), e.mb.types_bool())
    _fn_def(e, x, "h_operand", e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("cv", cve_t(e))), cve_t(e))
    fn_throws(e, "h_operand", errs_t(e))
    _fn_def(e, x, "h_args", e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("cv", cve_t(e))), _args_t(e))
    fn_throws(e, "h_args", errs_t(e))
    _fn_def(e, x, "h_const_str", e.rec(e.p("xx", xx_t(e)), e.p("cv", cve_t(e))), str_(e))
    _fn_def(e, x, "h_key_str", e.rec(e.p("xx", xx_t(e)), e.p("cv", cve_t(e))), str_(e))
    _fn_def(e, x, "h_gval", cve_t(e), cve_t(e))
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
    fn_impl(
        e,
        x,
        "h_is_js",
        body(e, e.ret(e.if_else(cve_has(e, a(e, "cv")), has(e, xx(e), cve_type(e, a(e, "cv")), "jany_m"), e.b(False)))),
    )
    fn_impl(
        e,
        x,
        "h_operand",
        body(
            e,
            e.if_only(e.not_(cve_has(e, a(e, "cv"))), throw_err(e, loc(e), "operand has no value")),
            e.ret(unwrap_cve_t(e, cast_value(e, xx(e), loc(e), _jany_t(e), a(e, "cv")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_args",
        body(
            e,
            e.let("out", _insts_new(e)),
            e.let("exprs", e.list_new(str_(e))),
            e.if_only(e.not_(cve_has(e, a(e, "cv"))), throw_err(e, loc(e), "call argument has no value")),
            e.let("tk", lookup(e, xx(e), cve_type(e, a(e, "cv")), asp_iface(e, "tuple"))),
            e.if_else(
                e.fld(e.v("tk"), "is_some"),
                e.foreach(
                    bim(
                        e,
                        asp_iface(e, "tuple"),
                        "take_elements",
                        e.fld(e.v("tk"), "value"),
                        e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, a(e, "cv")))),
                    ),
                    "er",
                    e.seq(
                        e.let("av", _operand(e, xx(e), loc(e), unwrap_cve_t(e, e.v("er")))),
                        _append_code(e, e.v("out"), cve_code(e, e.v("av"))),
                        push(e, e.v("exprs"), _jv_expr(e, e.v("av"))),
                    ),
                ),
                e.seq(
                    e.let("av", _operand(e, xx(e), loc(e), a(e, "cv"))),
                    _append_code(e, e.v("out"), cve_code(e, e.v("av"))),
                    push(e, e.v("exprs"), _jv_expr(e, e.v("av"))),
                ),
            ),
            e.ret(e.rec(e.p("code", _code_of(e, e.v("out"))), e.p("exprs", e.v("exprs")))),
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
        "h_gval",
        body(
            e,
            e.ret(
                cv_of(
                    e,
                    cve_code(e, e.v("arg")),
                    _jval_new(
                        e,
                        e.call(
                            e.mb.must_reinterpret(),
                            e.tup(
                                e.fld(
                                    e.call(e.mb.must_reinterpret(), e.tup(cve_value(e, e.v("arg")), voc_t(e))), "data"
                                ),
                                str_(e),
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
    accessor(e, x, "jval", "expr", str_(e))
    accessor(e, x, "jval", "ty", ty(e))
    accessor(e, x, "jval", "temp", bool_t(e))
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
    for vo in ["jinst", "jmod"]:
        marker_type(e, x, vo, vo, vo + "_m", e.aspect_dispatch(lv(e, vo + "_m_id")))
        x.append(e.impl_interface(e.v(vo), t(e, vo + "_m")))
    x.append(
        e.impl_interface(
            e.v("jbinding"),
            e.mb.eval_binding(),
            e.p("use", cv_of(e, a(e, "code"), _jval_new(e, in_(e, "name")))),
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
        e.rec(e.p("params", e.list_type(str_(e))), e.p("body", e.mb.types_expr())),
        cve_t(e),
        e.seq(
            e.let("entries", e.map_new(e.mb.types_constkey(), e.mb.eval_binding())),
            e.foreach(
                a(e, "params"),
                "pn",
                e.call_m(e.v("entries"), "put", e.tup(e.v("pn"), mk(e, "jbinding", e.p("name", e.v("pn"))))),
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
                        e.p("exception_type", str_(e)),
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
        e.rec(e.p("name", str_(e)), e.p("params", e.list_type(str_(e))), e.p("body", e.mb.types_expr())),
        str_(e),
        e.seq(
            e.let("fname", e.call_m(outer(e), "mint", a(e, "name"))),
            e.let("floc", e.call(e.eval_builtin("expr_loc"), a(e, "body"))),
            e.let("r", e.call_m(outer(e), "lower", e.rec(e.p("params", a(e, "params")), e.p("body", a(e, "body"))))),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, e.v("r"))),
            e.if_only(
                and_b(e, e.not_(cve_ended(e, e.v("r"))), _is_js(e, in_(e, "xx", "value"), e.v("r"))),
                push(e, e.v("out"), _inst(e, e.cat(e.s("return "), _jv_expr(e, e.v("r")), e.s(";")), e.v("floc"))),
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
                        e.call_m(outer(e), "lower", e.rec(e.p("params", e.list_new(str_(e))), e.p("body", e.v("arg")))),
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
            e.p("cast_exception", e.mb.panic(e.s("js target: exceptions are not supported"))),
            e.p(
                "initial_bind",
                e.eresult_err(
                    e.mb.eval_binding(), loc(e), e.s("js target: match and catch payloads are not supported")
                ),
            ),
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
            e.p("jump", e.mb.panic(e.s("js target: jumps are not supported"))),
            e.p("land", e.eresult_ok(cve_t(e), cv_no(e, code_none(e, loc(e))))),
            e.p("value_is_runtime", e.mb.bool(False)),
            structural_exits(e)[0],
            structural_exits(e)[1],
            e.p(
                "exit",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), a(e, "value", "code")),
                    e.if_only(
                        _is_js(e, xx(e), a(e, "value")),
                        e.seq(
                            push(
                                e,
                                e.v("out"),
                                _inst(e, e.cat(e.s("return "), _jv_expr(e, a(e, "value")), e.s(";")), loc(e)),
                            ),
                            ret_m(e, e.eresult_ok(code_t(e), _code_of(e, e.v("out")))),
                        ),
                    ),
                    push(e, e.v("out"), _inst(e, e.s("return;"), loc(e))),
                    e.ret(e.eresult_ok(code_t(e), _code_of(e, e.v("out")))),
                ),
            ),
            e.p("guarded", e.mb.panic(e.s("js target: exceptions are not supported"))),
            e.p("exc_cleanup", e.mb.panic(e.s("js target: exceptions are not supported"))),
            e.p("exit_trampoline", e.mb.panic(e.s("js target: cleanup blocks are not supported"))),
            e.p("drop", target_drop_body(e)),
            e.p(
                "return",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), a(e, "cv", "code")),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            e.if_else(
                                _is_js(e, xx(e), a(e, "cv")),
                                e.cat(e.s("return "), _jv_expr(e, a(e, "cv")), e.s(";")),
                                e.dstr("return;"),
                            ),
                            loc(e),
                        ),
                    ),
                    e.ret(e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("out")))),
                ),
            ),
            e.p("stage", err_cve(e, loc(e), "js target: nested staging is not supported")),
            e.p("if", _if_hook(e)),
            e.p("loop", err_cve(e, loc(e), "js target: loop is not supported")),
            e.p("try_catch_finally", err_cve(e, loc(e), "js target: try is not supported")),
            e.p("match", err_cve(e, loc(e), "js target: match is not supported")),
        )
    )

    self_type(
        e,
        x,
        "jany",
        e.s("js"),
        e.aspect_dispatch(
            lv(e, "jany_m_id"), asp_id(e, "function"), asp_id(e, "field"), asp_id(e, "bind"), asp_id(e, "set")
        ),
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), src_type(e)),
                    or_b(
                        e,
                        has(e, xx(e), src_type(e), "jglobal_m"),
                        or_b(
                            e,
                            has_b(e, xx(e), src_type(e), asp_iface(e, "record")),
                            or_b(
                                e,
                                has_b(e, xx(e), src_type(e), e.mb.eval_aspect_string_const()),
                                or_b(
                                    e,
                                    is_const(e, xx(e), src_type(e)),
                                    has_b(e, xx(e), src_type(e), e.eval_builtin("aspect_bool_const")),
                                ),
                            ),
                        ),
                    ),
                )
            ),
        ),
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(is_equal(e, xx(e), outer(e), e.v("st")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.if_only(has(e, xx(e), e.v("st"), "jglobal_m"), ret_m(e, ok_cve(e, hf(e, "h_gval", a(e, "cv"))))),
            e.if_only(
                has_b(e, xx(e), e.v("st"), e.mb.eval_aspect_string_const()),
                ret_m(
                    e,
                    ok_cve(
                        e, cv_of(e, code_none(e, loc(e)), _jval_new(e, hf(e, "h_str_lit", _const_str(e, a(e, "cv")))))
                    ),
                ),
            ),
            e.if_only(
                has_b(e, xx(e), e.v("st"), e.eval_builtin("aspect_bool_const")),
                ret_m(
                    e,
                    ok_cve(
                        e,
                        cv_of(
                            e,
                            code_none(e, loc(e)),
                            _jval_new(
                                e,
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
                    ),
                ),
            ),
            e.if_only(
                is_const(e, xx(e), e.v("st")),
                e.seq(
                    e.let(
                        "d",
                        e.call(
                            e.eval_builtin("const_numeric_to_double"),
                            e.rec(e.p("xx", xx(e)), e.p("value", cve_value(e, a(e, "cv")))),
                        ),
                    ),
                    e.let("l", e.mb.as_(e.v("d"), e.mb.types_long())),
                    ret_m(
                        e,
                        ok_cve(
                            e,
                            cv_of(
                                e,
                                code_none(e, loc(e)),
                                _jval_new(
                                    e,
                                    e.if_else(
                                        e.eq(e.mb.as_(e.v("l"), e.types_double()), e.v("d")),
                                        to_str(e, e.v("l")),
                                        to_str(e, e.v("d")),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            e.let("rk", lookup(e, xx(e), e.v("st"), asp_iface(e, "record"))),
            e.if_only(
                e.not_(e.fld(e.v("rk"), "is_some")),
                ret_m(e, err_cve(e, loc(e), "js: value cannot be converted to a js value")),
            ),
            e.let(
                "fields",
                bim(
                    e,
                    asp_iface(e, "record"),
                    "take_fields",
                    e.fld(e.v("rk"), "value"),
                    e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, a(e, "cv")))),
                ),
            ),
            e.let("out", _insts_new(e)),
            e.let("parts", e.list_new(str_(e))),
            e.foreach(
                bim0(e, asp_iface(e, "record"), "field_types", e.fld(e.v("rk"), "value")),
                "en",
                e.seq(
                    e.let("ks", key_str(e, e.fld(e.v("en"), "key"))),
                    e.let("fcv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.v("ks")))),
                    e.let("fv", unwrap_cve_m(e, try_er(e, _operand(e, xx(e), loc(e), e.v("fcv")), cve_t(e)))),
                    _append_code(e, e.v("out"), cve_code(e, e.v("fv"))),
                    push(e, e.v("parts"), e.cat(e.v("ks"), e.s(": "), _jv_expr(e, e.v("fv")))),
                ),
            ),
            e.ret(
                ok_cve(
                    e,
                    cv_of(
                        e, _code_of(e, e.v("out")), _jval_new(e, e.cat(e.s("{"), e.join(e.v("parts"), ", "), e.s("}")))
                    ),
                )
            ),
        ),
        body(e, e.ret(is_equal(e, xx(e), outer(e), a(e, "dest_type")))),
        cast_from_self(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "jany_m"))),
    )
    x.append(e.impl_interface(e.v("jany"), t(e, "jany_m")))
    x.append(
        e.impl_interface(
            e.v("jany"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    e.let("f", unwrap_cve_m(e, try_er(e, _operand(e, xx(e), loc(e), a(e, "function")), cve_t(e)))),
                    _append_code(e, e.v("out"), cve_code(e, e.v("f"))),
                    e.let("args", _args_of(e)),
                    _append_code(e, e.v("out"), e.fld(e.v("args"), "code")),
                    e.let("r", _fresh(e, _xmod(e))),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            e.cat(
                                e.s("const "),
                                e.v("r"),
                                e.s(" = "),
                                _jv_expr(e, e.v("f")),
                                e.s("("),
                                e.join(e.fld(e.v("args"), "exprs"), ", "),
                                e.s(");"),
                            ),
                            loc(e),
                        ),
                    ),
                    e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _jval_temp(e, e.v("r"))))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )
    x.append(
        e.impl_interface(
            e.v("jany"),
            asp_iface(e, "field"),
            e.p(
                "field",
                body(
                    e,
                    e.let("s", unwrap_cve_m(e, try_er(e, _operand(e, xx(e), loc(e), a(e, "value")), cve_t(e)))),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("s"))),
                    e.if_only(
                        has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const()),
                        ret_m(
                            e,
                            ok_cve(
                                e,
                                cv_of(
                                    e,
                                    _code_of(e, e.v("out")),
                                    _jval_new(
                                        e,
                                        e.cat(
                                            _jv_expr(e, e.v("s")),
                                            e.s("."),
                                            hf_rec(e, "h_key_str", e.p("xx", xx(e)), e.p("cv", a(e, "key"))),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.let("k", unwrap_cve_m(e, try_er(e, _operand(e, xx(e), loc(e), a(e, "key")), cve_t(e)))),
                    _append_code(e, e.v("out"), cve_code(e, e.v("k"))),
                    e.ret(
                        ok_cve(
                            e,
                            cv_of(
                                e,
                                _code_of(e, e.v("out")),
                                _jval_new(e, e.cat(_jv_expr(e, e.v("s")), e.s("["), _jv_expr(e, e.v("k")), e.s("]"))),
                            ),
                        )
                    ),
                ),
            ),
            e.p("type_opt", e.option_type_lowered_none()),
            e.p("keys", e.list_new(e.mb.types_constkey())),
        )
    )
    x.append(
        e.impl_interface(
            e.v("jany"),
            e.mb.eval_aspect_set(),
            e.p(
                "set",
                body(
                    e,
                    e.let("t", unwrap_cve_m(e, try_er(e, _operand(e, xx(e), loc(e), a(e, "target")), cve_t(e)))),
                    e.let("v", unwrap_cve_m(e, try_er(e, _operand(e, xx(e), loc(e), a(e, "value")), cve_t(e)))),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("t"))),
                    _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                    push(
                        e,
                        e.v("out"),
                        _inst(e, e.cat(_jv_expr(e, e.v("t")), e.s(" = "), _jv_expr(e, e.v("v")), e.s(";")), loc(e)),
                    ),
                    e.ret(ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                ),
            ),
        )
    )
    br_t = e.mb.types_bind_result()
    x.append(
        e.impl_interface(
            e.v("jany"),
            e.mb.eval_aspect_bind(),
            e.p(
                "bind",
                body(
                    e,
                    e.let("v", unwrap_m(e, try_er(e, _operand(e, xx(e), loc(e), a(e, "cv")), cve_t(e)), br_t)),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                    # A value already in a fresh `const` of its own is the binding; anything else is copied into one.
                    e.let("jv", reinterpret(e, cve_value(e, e.v("v")), "jval")),
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
                                e, e.cat(e.s("const "), e.v("r"), e.s(" = "), _jv_expr(e, e.v("v")), e.s(";")), loc(e)
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
                                    e.p("binding", mk(e, "jbinding", e.p("name", e.v("r")))),
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    )

    self_type(
        e,
        x,
        "jglobal",
        e.s("js global"),
        rt_dispatch(
            e,
            e.mb.types_string(),
            e.aspect_dispatch(lv(e, "jglobal_m_id"), asp_id(e, "function"), asp_id(e, "field"), asp_id(e, "set")),
        ),
        can_cast_from_self(e),
        cast_from_self(e),
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), a(e, "dest_type")),
                    is_equal(e, xx(e), _jany_t(e), a(e, "dest_type")),
                )
            ),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), a(e, "dest_type")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.ret(cast_value(e, xx(e), loc(e), a(e, "dest_type"), hf(e, "h_gval", a(e, "cv")))),
        ),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "jglobal_m"))),
    )
    x.append(e.impl_interface(e.v("jglobal"), t(e, "jglobal_m")))
    rt_lift_impl(e, x, "jglobal")
    rt_bind_impl(e, x, "jglobal", e.mb.types_string())
    rt_use_impl(e, x, "jglobal")
    for asp in ["function", "field", "set"]:
        method_name = "call" if asp == "function" else asp
        if asp == "function":
            extra = [e.p("argument", a(e, "argument"))]
        elif asp == "field":
            extra = [e.p("key", a(e, "key"))]
        else:
            extra = [e.p("value", a(e, "value"))]
        call_args = []
        call_args.append(e.p("xx", xx(e)))
        call_args.append(e.p("loc", loc(e)))
        recv = {"function": "function", "field": "value", "set": "target"}[asp]
        call_args.append(e.p(recv, hf(e, "h_gval", a(e, recv))))
        for pair in extra:
            call_args.append(pair)
        ps = []
        ps.append(
            e.p(
                method_name,
                body(
                    e,
                    e.ret(
                        bim(
                            e,
                            asp_iface(e, asp),
                            method_name,
                            lookup_v(e, xx(e), _jany_t(e), asp_iface(e, asp)),
                            e.rec(*call_args),
                        )
                    ),
                ),
            )
        )
        if asp == "function":
            ps.append(e.p("exception_type", e.option_type_lowered_none()))
        elif asp == "field":
            ps.append(e.p("type_opt", e.option_type_lowered_none()))
            ps.append(e.p("keys", e.list_new(e.mb.types_constkey())))
        iface = e.mb.eval_aspect_set() if asp == "set" else asp_iface(e, asp)
        x.append(e.impl_interface(e.v("jglobal"), iface, *ps))

    self_type(
        e,
        x,
        "jnew",
        e.s("js new"),
        rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(lv(e, "jnew_m_id"), asp_id(e, "function"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "jnew_m"))),
    )
    x.append(e.impl_interface(e.v("jnew"), t(e, "jnew_m")))
    rt_lift_impl(e, x, "jnew")
    rt_bind_impl(e, x, "jnew", e.mb.types_string())
    rt_use_impl(e, x, "jnew")
    x.append(
        e.impl_interface(
            e.v("jnew"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("args", _args_of(e)),
                    count_let(e, "na"),
                    count_loop(e, "na", e.fld(e.v("args"), "exprs")),
                    e.if_only(
                        e.eq(e.fld(e.v("na"), "v"), num(e, 0)),
                        ret_m(e, err_cve(e, loc(e), "js new: the first argument is the constructor")),
                    ),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), e.fld(e.v("args"), "code")),
                    e.let("rest", e.list_new(str_(e))),
                    e.let("ctor", e.rec(e.p("v", e.dstr("")))),
                    e.foreach(
                        e.fld(e.v("args"), "exprs"),
                        "ax",
                        e.if_else(
                            e.eq(e.fld(e.v("ctor"), "v"), e.s("")),
                            e.mb.set(e.fld(e.v("ctor"), "v"), e.v("ax")),
                            push(e, e.v("rest"), e.v("ax")),
                        ),
                    ),
                    e.let("r", _fresh(e, _xmod(e))),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            e.cat(
                                e.s("const "),
                                e.v("r"),
                                e.s(" = new "),
                                e.fld(e.v("ctor"), "v"),
                                e.s("("),
                                e.join(e.v("rest"), ", "),
                                e.s(");"),
                            ),
                            loc(e),
                        ),
                    ),
                    e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _jval_temp(e, e.v("r"))))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )

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
            e.if_only(
                _jgfn_is(e, "new_fn"),
                ret_m(e, tag_value(e, _jgfn_staged(e, e.s("new")), mk_arg(e, "jnew", e.tup()))),
            ),
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
            e.let("namecv", _jgfn_staged(e, graft(e, _jgfn_field(e, "name")))),
            e.if_only(
                is_runtime(e, e.v("namecv")),
                ret_m(e, err_cve(e, loc(e), "js definition name must be constant")),
            ),
            e.let("name", _const_str(e, e.v("namecv"))),
            e.if_only(_jgfn_is(e, "global_fn"), ret_m(e, tag_value(e, e.v("namecv"), mk_arg(e, "jglobal", e.tup())))),
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
                    ret_m(e, tag_value(e, e.v("varcv"), mk_arg(e, "jglobal", e.tup()))),
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
                            e.p("body", graft(e, e.v("bodycv"))),
                        ),
                    ),
                ),
            ),
            e.ret(tag_value(e, e.v("refcv"), mk_arg(e, "jglobal", e.tup()))),
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
                                e.p("exception_type", str_(e)),
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
    for obj in ["jany", "jglobal", "jgfn_t"]:
        defs.append(e.p(obj + "_new", e.fld(e.v(obj), "new")))
    x.append(e.ret(e.rec(*defs)))

    y = []
    y.append(e.let("k", e.lower(e.mb.seq(x))))
    exported = []
    exported.append("any")
    y.append(e.let("any", e.mb.as_(e.call(e.fld(e.v("k"), "jany_new"), e.tup()), ty(e))))
    exported.append("global")
    y.append(e.let("global", e.mb.as_(e.call(e.fld(e.v("k"), "jglobal_new"), e.tup()), ty(e))))
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
