"""Shorthand builders over `Mb` shared by every ecosystem module."""

from .mb import Mb
from .registry import project_of


def p(key, value):
    """Record pair: (key string, value expr)."""
    return (key, value)


class EcoMb:
    """Expression shorthands for the builders. `project` is the building module's project (registry.py), which
    `import_local` uses to place other modules; None for a builder outside the registry."""

    def __init__(self, project=None):
        self.project = project
        self.fn_sigs = {}
        self.mb = Mb()

    def v(self, name):
        return self.mb.scope_use(name)

    def s(self, value):
        return self.mb.str(value)

    def n(self, value):
        return self.mb.num(value)

    def b(self, value):
        return self.mb.bool(value)

    def int_of(self, value):
        return self.mb.as_(self.mb.num(value), self.mb.types_int())

    def let(self, name, value):
        return self.mb.bind(name, value)

    def fld(self, base, *keys):
        expr = base
        for key in keys:
            expr = self.mb.field(expr, self.mb.str(key))
        return expr

    def call(self, func, arg):
        return self.mb.call(func, arg)

    def pipe(self, self_, func, arg):
        return self.mb.pipe(self_, func, arg)

    def call_m(self, receiver, method, arg):
        return self.mb.call(self.fld(receiver, method), arg)

    def call_m0(self, receiver, method):
        return self.call_m(receiver, method, self.mb.tuple_of())

    def p(self, key, value):
        return p(key, value)

    def rec(self, *pairs):
        return self.mb.record_of(list(pairs))

    def seq(self, *exprs):
        return self.mb.seq_of(*exprs)

    def tup(self, *exprs):
        return self.mb.tuple_of(*exprs)

    def ret(self, value):
        return self.mb.return_(value)

    def list_type(self, element_type):
        return self.mb.call(self.mb.types_list(), element_type)

    def list_new(self, element_type, *elements):
        return self.call_m(self.list_type(element_type), "new", self.mb.tuple_of(*elements))

    def str_list(self, *elements):
        return self.list_new(self.mb.types_string(), *elements)

    def push(self, list_, element):
        return self.call_m(list_, "push", element)

    def join(self, list_, separator):
        return self.call_m(list_, "join", self.mb.str(separator))

    def cat(self, *parts):
        return self.join(self.str_list(*parts), "")

    def to_str(self, value):
        return self.call_m0(value, "to_string")

    def foreach(self, base, element_name, body):
        return self.mb.foreach(base, self.mb.str(element_name), body)

    def if_else(self, condition, then, else_):
        return self.mb.if_of([(condition, then)], else_)

    def if_only(self, condition, then):
        return self.mb.if_of([(condition, then)], None)

    def incr(self, base):
        return self.mb.set(base, self.mb.operator_add(base, self.mb.num(1.0)))

    def opt_some(self, element_type, value):
        return self.call_m(self.mb.call(self.mb.types_option(), element_type), "some", value)

    def opt_none(self, element_type):
        return self.call_m(self.mb.call(self.mb.types_option(), element_type), "none", self.mb.tuple_of())

    def option_type_let(self):
        return self.let("option_type", self.mb.call(self.mb.types_option(), self.mb.eval_type()))

    def option_type_some(self, type_expr):
        return self.call_m(self.v("option_type"), "some", type_expr)

    def option_type_none(self):
        return self.call_m(self.v("option_type"), "none", self.mb.tuple_of())

    def option_type_lowered_some(self, type_expr):
        return self.call_m(self.lower_v("option_type"), "some", type_expr)

    def option_type_lowered_none(self):
        return self.call_m(self.lower_v("option_type"), "none", self.mb.tuple_of())

    def stage(self, expr):
        return self.mb.stage(expr)

    def lower(self, expr):
        return self.mb.lower(expr)

    def lower_v(self, name):
        return self.mb.lower(self.mb.scope_use(name))

    def define(self):
        return self.mb.call(self.mb.define(), self.mb.tuple_of())

    def def_func(self, definer, name):
        return self.call_m(definer, "func", self.mb.str(name))

    def def_object(self, definer, name):
        return self.call_m(definer, "object", self.mb.str(name))

    def finish(self, definer):
        return self.call_m0(definer, "finish")

    def func_impl(self, func_builder, arg, ret, exception_type, staged_body):
        return self.call_m(
            func_builder,
            "impl",
            self.rec(
                p("arg", arg),
                p("ret", ret),
                p("impl_body", staged_body),
                p("exception_type", exception_type),
                p("description", self.opt_none(self.mb.types_string())),
            ),
        )

    def method_impl(self, object_builder, name, arg, ret, staged_body):
        return self.call_m(
            self.call_m(object_builder, "func", self.mb.str(name)),
            "impl",
            self.rec(p("arg", arg), p("ret", ret), p("impl_body", staged_body)),
        )

    def object_impl(self, object_builder, inner):
        return self.call_m(
            object_builder, "impl", self.rec(p("inner", inner), p("description", self.opt_none(self.mb.types_string())))
        )

    def interface_impl(self, interface_builder, is_aspect):
        return self.call_m(
            interface_builder,
            "impl",
            self.rec(p("is_aspect", self.b(is_aspect)), p("description", self.opt_none(self.mb.types_string()))),
        )

    def import_local(self, key, path):
        """Imports a local file: a registered module by its bare file name (its project's directory comes from the
        registry, relative to this builder's project), or any other file by a path relative to this module's."""
        return self.mb.field(self.mb.import_record([(self.mb.str(key), self.source_local(path))]), self.mb.str(key))

    def source_local(self, path):
        try:
            target = project_of(path)
        except KeyError:
            return self.mb.source_local(self.mb.str(path))
        if self.project is None:
            raise ValueError("import of the module " + path + " from a builder with no project")
        rel = path if target == self.project else "../" + target + "/" + path
        return self.mb.source_local(self.mb.str(rel))

    def import_git(self, key, url, commit):
        entry = (self.mb.str(key), self.mb.source_git(self.mb.str(url), self.mb.str(commit)))
        return self.mb.field(self.mb.import_record([entry]), self.mb.str(key))

    def impl_interface(self, object_builder, iface_ref, *methods):
        staged = []
        for key, value in methods:
            staged.append((key, self.mb.stage(value)))
        record = self.mb.call(
            self.mb.field(
                self.mb.call(self.mb.types_map(), self.mb.tuple_of(self.mb.types_constkey(), self.mb.types_expr())),
                self.mb.str("new"),
            ),
            self.mb.record_of(staged),
        )
        return self.call_m(object_builder, "impl_interface", self.rec(p("iface_ref", iface_ref), p("record", record)))

    def eresult_ok(self, result_type, value):
        return self.call_m(self.mb.call(self.mb.types_eresult(), result_type), "ok", value)

    def eresult_err(self, result_type, loc, message):
        return self.call_m(self.mb.call(self.mb.types_eresult(), result_type), "err", self.mb.tuple_of(loc, message))

    def eresult_errs(self, result_type, errors):
        return self.call_m(self.mb.call(self.mb.types_eresult(), result_type), "errs", errors)

    def types_double(self):
        return self.mb.builtin("types", "double")

    def types_float(self):
        return self.mb.builtin("types", "float")

    def types_expr_context(self):
        return self.mb.builtin("types", "expr_context")

    def types_loc(self):
        return self.mb.builtin("types", "qexpr_id")

    def types_jump_key(self):
        return self.mb.builtin("types", "jump_key")

    def eval_builtin(self, name):
        return self.mb.builtin("eval", name)

    def dstr(self, value):
        return self.mb.as_(self.mb.str(value), self.mb.types_string())

    def match_of(self, base, key, fallback, *branches):
        """`fallback`: expr or None; `branches`: (tag, body) pairs."""
        out = []
        for tag, body in branches:
            out.append((self.mb.str(tag), body))
        return self.mb.match_of(base, self.mb.str(key), out, fallback)

    def map_type(self, key_type, value_type):
        return self.mb.call(self.mb.types_map(), self.mb.tuple_of(key_type, value_type))

    def map_new(self, key_type, value_type, *entries):
        return self.call_m(self.map_type(key_type, value_type), "new", self.rec(*entries))

    def not_(self, a):
        return self.mb.operator_bit_not(a)

    def eq(self, a, b):
        return self.mb.operator_eq(a, b)

    def aspect_dispatch(self, *aspect_ids):
        branches = []
        for aspect_id in aspect_ids:
            branches.append(
                (
                    self.mb.operator_eq(self.fld(self.v("arg"), "key"), aspect_id),
                    self.opt_some(self.mb.types_aspect(), self.v("outer")),
                )
            )
        return self.mb.if_of(branches, self.opt_none(self.mb.types_aspect()))
