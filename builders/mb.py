"""Source-expression builder: one `Mb` per module, ids assigned in construction order.

Nodes are plain dicts in the SourceModule JSON shape (`{"id": n, "variant": {...}}`), with
variant fields inserted in codec order so the serialized module matches the Java codec byte for byte.
"""

import math
import re


def _opt(value):
    return {"none": None} if value is None else {"some": value}


class Mb:
    def __init__(self):
        self._next_id = 0

    def _id(self):
        node_id = self._next_id
        self._next_id += 1
        return node_id

    def _node(self, kind, fields):
        return {"id": self._id(), "variant": {kind: fields}}

    def num(self, value):
        return self._node("literal", {"number": float(value)})

    def str(self, value):
        return self._node("literal", {"str": value})

    def bool(self, value):
        return self._node("literal", {"bool": value})

    def as_(self, base, target):
        return self._node("as", {"base": base, "target": target})

    def bind(self, name, value):
        node_id = self._id()
        return {"id": node_id, "variant": {"bind": {"name": self.str(name), "value": value}}}

    def call(self, func, arg):
        return self._node("call", {"func": func, "arg": arg})

    def pipe(self, self_, func, arg):
        """`self_ | func arg`: calls `func` with `self_` spliced into `arg` (prepended to a tuple, the `self` field of
        a record, else `(self_, arg)`)."""
        return self._node("pipe", {"self": self_, "func": func, "arg": arg})

    def field(self, base, key):
        return self._node("field", {"base": base, "key": key})

    def foreach(self, base, element_key, body):
        return self._node("foreach", {"base": base, "element_key": element_key, "body": body})

    def graft(self, expr):
        return self._node("graft", expr)

    def source_local(self, path):
        return self.call(self.builtin("source", "local"), path)

    def source_git(self, url, commit):
        return self.call(self.builtin("source", "remote", "git"), self.tuple([url, commit]))

    def import_record(self, entries):
        """`entries`: list of (key expr, value expr)."""
        return self.call(self.builtin("import"), self.record(entries))

    def loop(self, body):
        return self._node("loop", body)

    def labeled(self, label, inner):
        return self._node("labeled", {"label": label, "inner": inner})

    def _return(self, label, value):
        return self._node("return", {"label": _opt(label), "value": _opt(value)})

    def return_(self, value):
        return self._return(None, value)

    def return_to(self, label, value):
        return self._return(label, value)

    def return_label(self, label):
        return self._return(label, None)

    def lower(self, expr):
        return self._node("lower", expr)

    def operator_binary(self, op, base, reference):
        return self._node("operator_binary", {"op": op, "base": base, "reference": reference})

    def operator_unary(self, op, base):
        return self._node("operator_unary", {"op": op, "base": base})

    def operator_add(self, base, reference):
        return self.operator_binary("add", base, reference)

    def operator_sub(self, base, reference):
        return self.operator_binary("sub", base, reference)

    def operator_mul(self, base, reference):
        return self.operator_binary("mul", base, reference)

    def operator_div(self, base, reference):
        return self.operator_binary("div", base, reference)

    def operator_mod(self, base, reference):
        return self.operator_binary("mod", base, reference)

    def operator_and(self, base, reference):
        return self.operator_binary("and", base, reference)

    def operator_or(self, base, reference):
        return self.operator_binary("or", base, reference)

    def operator_xor(self, base, reference):
        return self.operator_binary("xor", base, reference)

    def operator_shl(self, base, reference):
        return self.operator_binary("shl", base, reference)

    def operator_shr(self, base, reference):
        return self.operator_binary("shr", base, reference)

    def operator_ushr(self, base, reference):
        return self.operator_binary("ushr", base, reference)

    def operator_eq(self, base, reference):
        return self.operator_binary("eq", base, reference)

    def operator_ne(self, base, reference):
        return self.operator_binary("ne", base, reference)

    def operator_lt(self, base, reference):
        return self.operator_binary("lt", base, reference)

    def operator_le(self, base, reference):
        return self.operator_binary("le", base, reference)

    def operator_gt(self, base, reference):
        return self.operator_binary("gt", base, reference)

    def operator_ge(self, base, reference):
        return self.operator_binary("ge", base, reference)

    def operator_neg(self, base):
        return self.operator_unary("neg", base)

    def operator_bit_not(self, base):
        return self.operator_unary("bitnot", base)

    def record(self, entries):
        """`entries`: list of (key expr, value expr)."""
        return self._node("record", [{"key": k, "value": v} for k, v in entries])

    def scope_use(self, key):
        node_id = self._id()
        return {"id": node_id, "variant": {"scope_use": self.str(key)}}

    def seq(self, exprs):
        return self._node("seq", list(exprs))

    def set(self, base, value):
        return self._node("set", {"base": base, "value": value})

    def stage(self, expr):
        return self._node("stage", expr)

    def tuple(self, values):
        return self._node("tuple", list(values))

    def builtin(self, *path):
        expr = self.scope_use("builtins")
        for segment in path:
            expr = self.field(expr, self.str(segment))
        return expr

    def log(self):
        return self.builtin("log")

    def panic(self, message):
        return self.call(self.builtin("panic"), message)

    def throw_(self, value):
        return self.call(self.builtin("throw"), value)

    def define(self):
        return self.builtin("define")

    def eval_aspect_lookup(self):
        return self.builtin("eval", "aspect_lookup")

    def eval_aspect_field_use_dynamic(self):
        return self.builtin("eval", "aspect_field_use_dynamic")

    def eval_aspect_set(self):
        return self.builtin("eval", "aspect_set")

    def must_reinterpret(self):
        return self.builtin("must_reinterpret")

    def reinterpret(self):
        return self.builtin("reinterpret")

    def eval_value(self):
        return self.builtin("eval", "value")

    def eval_type(self):
        return self.builtin("eval", "type")

    def eval_binding(self):
        return self.builtin("eval", "binding")

    def eval_aspect_bind(self):
        return self.builtin("eval", "aspect_bind")

    def eval_aspect_initial_bind(self):
        return self.builtin("eval", "aspect_initial_bind")

    def eval_binding_slot(self):
        return self.builtin("eval", "binding_slot")

    def eval_binding_slot_dynamic(self):
        return self.builtin("eval", "binding_slot_dynamic")

    def eval_aspect_lift(self):
        return self.builtin("eval", "aspect_lift")

    def eval_aspect_int(self):
        return self.builtin("eval", "aspect_int")

    def eval_aspect_string_const(self):
        return self.builtin("eval", "aspect_string_const")

    def eval_str_utf8(self):
        return self.builtin("eval", "str_utf8")

    def eval_aspect_drop_dynamic_id(self):
        return self.builtin("eval", "aspect_drop_dynamic_id")

    def eval_aspect_consume_dynamic_id(self):
        return self.builtin("eval", "aspect_consume_dynamic_id")

    def eval_aspect_bind_dynamic_id(self):
        return self.builtin("eval", "aspect_bind_dynamic_id")

    def eval_aspect_drop_dynamic(self):
        return self.builtin("eval", "aspect_drop_dynamic")

    def eval_drop_value(self):
        return self.builtin("eval", "drop_value")

    def eval_binding_setter_consumed(self):
        return self.builtin("eval", "binding_setter_consumed")

    def eval_exit_value(self):
        return self.builtin("eval", "exit_value")

    def types_exit_value(self):
        return self.builtin("types", "exit_value")

    def eval_bind_result(self):
        return self.builtin("eval", "bind_result")

    def eval_codevalue(self):
        return self.builtin("eval", "codevalue")

    def eval_const_eval(self):
        return self.builtin("eval", "const_eval")

    def eval_target(self):
        return self.builtin("eval", "target")

    def types_aspect(self):
        return self.builtin("types", "aspect")

    def types_bool(self):
        return self.builtin("types", "bool")

    def types_bind_result(self):
        return self.builtin("types", "bind_result")

    def types_constkey(self):
        return self.builtin("types", "constkey")

    def types_cve(self):
        return self.builtin("types", "cve")

    def types_eresult(self):
        return self.builtin("types", "eresult")

    def types_code(self):
        return self.builtin("types", "code")

    def types_expr(self):
        return self.builtin("types", "expr")

    def types_list(self):
        return self.builtin("types", "list")

    def types_array(self):
        return self.builtin("types", "array")

    def types_map(self):
        return self.builtin("types", "map")

    def types_int_box(self):
        return self.builtin("types", "int_box")

    def types_int(self):
        return self.builtin("types", "int")

    def types_byte(self):
        return self.builtin("types", "byte")

    def types_long(self):
        return self.builtin("types", "long")

    def types_option(self):
        return self.builtin("types", "option")

    def opt_some_type(self, type_expr):
        return self.call(self.field(self.call(self.types_option(), self.eval_type()), self.str("some")), type_expr)

    def opt_none_type(self):
        return self.call(
            self.field(self.call(self.types_option(), self.eval_type()), self.str("none")), self.tuple_of()
        )

    def opt_none_string(self):
        return self.call(
            self.field(self.call(self.types_option(), self.types_string()), self.str("none")), self.tuple_of()
        )

    def types_string(self):
        return self.builtin("types", "string")

    def types_unique(self):
        return self.builtin("types", "unique")

    def seq_of(self, *exprs):
        return self.seq(exprs)

    def tuple_of(self, *values):
        return self.tuple(values)

    def record_of(self, entries):
        """`entries`: list of (key string, value expr)."""
        out = []
        for key, value in entries:
            out.append((self.str(key), value))
        return self.record(out)

    def if_of(self, cases, else_body):
        """`cases`: list of (condition, body); `else_body`: expr or None."""
        return self._node(
            "if",
            {"conditions": [{"condition": c, "body": b} for c, b in cases], "fallback": _opt(else_body)},
        )

    def match_of(self, base, element_key, cases, fallback):
        """`cases`: list of (condition, body); `fallback`: expr or None."""
        return self._node(
            "match",
            {
                "base": base,
                "element_key": element_key,
                "cases": [{"condition": c, "body": b} for c, b in cases],
                "fallback": _opt(fallback),
            },
        )

    def try_catch_finally(self, body, catch_clause, finally_block):
        """`catch_clause`: (binding name, exception type, body) or None; `finally_block`: expr or None."""
        if catch_clause is None:
            catch = None
        else:
            name, exception_type, catch_body = catch_clause
            catch = {"binding_name": self.str(name), "exception_type": exception_type, "body": catch_body}
        return self._node("try", {"body": body, "catch_clause": _opt(catch), "finally_block": _opt(finally_block)})


def _java_double(value):
    """Java `Double.toString` (shortest repr digits, JDK 19+ layout)."""
    if value == 0:
        return "-0.0" if math.copysign(1.0, value) < 0 else "0.0"
    sign = "-" if value < 0 else ""
    parsed = re.fullmatch(r"(\d+)(?:\.(\d+))?(?:e([+-]\d+))?", repr(abs(value)))
    int_part, frac_part, exp_part = parsed.group(1), parsed.group(2) or "", parsed.group(3)
    all_digits = int_part + frac_part
    digits = all_digits.lstrip("0")
    # value = 0.<digits> * 10^point
    point = len(int_part) - (len(all_digits) - len(digits)) + (int(exp_part) if exp_part else 0)
    digits = digits.rstrip("0")
    if 1e-3 <= abs(value) < 1e7:
        if point <= 0:
            return f"{sign}0.{'0' * -point}{digits}"
        if point >= len(digits):
            return f"{sign}{digits}{'0' * (point - len(digits))}.0"
        return f"{sign}{digits[:point]}.{digits[point:]}"
    sci_exp = point - 1
    frac = digits[1:] or "0"
    return f"{sign}{digits[0]}.{frac}E{sci_exp}"


_ESCAPES = {'"': '\\"', "\\": "\\\\", "\t": "\\t", "\b": "\\b", "\n": "\\n", "\r": "\\r", "\f": "\\f"}
_ESCAPE_RE = re.compile('["\\\\\x00-\x1f  ]')


def _escape(match):
    ch = match.group(0)
    escaped = _ESCAPES.get(ch)
    return escaped if escaped is not None else f"\\u{ord(ch):04x}"


def _encode(value, out):
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, float):
        out.append(_java_double(value))
    elif isinstance(value, int):
        out.append(str(value))
    elif isinstance(value, str):
        out.append('"' + _ESCAPE_RE.sub(_escape, value) + '"')
    elif isinstance(value, list):
        out.append("[")
        for i, element in enumerate(value):
            if i:
                out.append(",")
            _encode(element, out)
        out.append("]")
    else:
        out.append("{")
        for i, (key, element) in enumerate(value.items()):
            if i:
                out.append(",")
            out.append('"' + key + '":')
            _encode(element, out)
        out.append("}")


def module_json(exprs):
    """Compact SourceModule JSON matching the Java codec output."""
    out = []
    _encode({"v1": exprs}, out)
    return "".join(out)
