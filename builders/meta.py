"""meta.atz: the json-like `value_t` union carried in code metadata."""

FILE = "meta.atz"

VARIANTS = ["str", "int", "float", "bool", "list", "map"]


def _value_t(e):
    return e.fld(e.v("value_u"), "type")


def module(e):
    top = []
    top.append(e.let("d", e.define()))
    top.append(e.let("value_u", e.call_m0(e.v("d"), "union")))
    for tag in VARIANTS:
        if tag == "str":
            type_ref = e.mb.types_string()
        elif tag == "int":
            type_ref = e.mb.types_int()
        elif tag == "float":
            type_ref = e.types_double()
        elif tag == "bool":
            type_ref = e.mb.types_bool()
        elif tag == "list":
            type_ref = e.list_type(_value_t(e))
        elif tag == "map":
            type_ref = e.map_type(e.mb.types_string(), _value_t(e))
        else:
            raise AssertionError(tag)
        top.append(
            e.let(
                "v_" + tag, e.call_m(e.v("value_u"), "variant", e.rec(e.p("tag", e.s(tag)), e.p("type_ref", type_ref)))
            )
        )
    top.append(e.finish(e.v("d")))
    defs = []
    defs.append(e.p("value_t", _value_t(e)))
    defs.append(e.p("other_t", e.rec(e.p("type", e.mb.types_string()), e.p("value", _value_t(e)))))
    for tag in VARIANTS:
        defs.append(e.p(tag, e.v("v_" + tag)))
    top.append(e.ret(e.rec(*defs)))
    return top
