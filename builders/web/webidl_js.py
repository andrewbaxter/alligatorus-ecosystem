"""webidl-js.atz: JS glue for WebIDL bindings (handle table with a free list, string decoding, generated wrapper
functions). The `release` import frees a handle; webidl-wasm.atz calls it when an owned handle is dropped."""

from ..target_mb import body, or_b, ret_m, to_str


def _var(e, name):
    return e.call(e.lower(e.fld(e.v("js"), "var_fn")), e.rec(e.p("mod", e.v("m")), e.p("name", e.s(name))))


def _text(e, name, params, *lines):
    """A function of plain lines in the module `m`, named from the hint `name`; its minted name."""
    return e.call_m(
        e.v("m"),
        "func_text",
        e.rec(
            e.p("name", e.s(name)),
            e.p("params", e.list_new(e.mb.types_string(), *params)),
            e.p("lines", e.list_new(e.mb.types_string(), *lines)),
        ),
    )


def _rt_t(e):
    """What `runtime` yields: the minted names of the runtime's helpers, which the wrappers `define` makes refer
    to."""
    return e.rec(
        e.p("h_new", e.mb.types_string()),
        e.p("h_get", e.mb.types_string()),
        e.p("h_free", e.mb.types_string()),
        e.p("str", e.mb.types_string()),
    )


def _rt(e, field):
    return e.fld(e.fld(e.v("arg"), "rt"), field)


def _sig(e, field):
    return e.call_m(e.v("sig"), field, e.tup())


def _line(e, *parts):
    return e.push(e.v("lines"), e.cat(*parts))


def _param(e, *parts):
    return e.push(e.v("params"), e.cat(*parts))


def _kind_is(e, kind, *names):
    expr = e.eq(kind, e.s(names[-1]))
    for i in range(len(names) - 2, -1, -1):
        expr = or_b(e, e.eq(kind, e.s(names[i])), expr)
    return expr


def module(e):
    top = []
    top.append(e.let("js", e.import_local("js", "js-es2020.atz")))
    top.append(e.let("webidl", e.import_local("webidl", "webidl.atz")))
    top.append(e.let("d", e.define()))
    top.append(e.option_type_let())

    top.append(e.let("runtime_b", e.def_func(e.v("d"), "runtime")))
    runtime = []
    runtime.append(e.let("m", e.fld(e.v("arg"), "mod")))
    # The module variables, which the text below refers to by name; `instance` is assigned by the caller when the
    # wasm module is ready.
    for g in ["handles", "free_handles", "freed", "instance", "decoder"]:
        runtime.append(e.let(g, _var(e, g)))
    for g in ["Array", "Object", "TextDecoder"]:
        runtime.append(e.let(g, e.call(e.lower(e.fld(e.v("js"), "global_fn")), e.rec(e.p("name", e.s(g))))))
    runtime.append(e.let("new", e.call(e.lower(e.fld(e.v("js"), "new_fn")), e.tup())))
    runtime.append(
        e.call_m(
            e.v("m"),
            "run",
            e.stage(
                e.seq(
                    e.mb.set(e.lower(e.v("handles")), e.call(e.lower(e.v("new")), e.lower(e.v("Array")))),
                    e.mb.set(e.lower(e.v("free_handles")), e.call(e.lower(e.v("new")), e.lower(e.v("Array")))),
                    # The marker a freed slot holds (distinct from every value a handle can hold, `undefined`
                    # included), so a use or a second free of a freed handle throws instead of reading a stale slot.
                    e.mb.set(e.lower(e.v("freed")), e.call(e.lower(e.v("new")), e.lower(e.v("Object")))),
                    e.mb.set(e.lower(e.v("decoder")), e.call(e.lower(e.v("new")), e.lower(e.v("TextDecoder")))),
                )
            ),
        )
    )
    # The handle table reuses freed slots; these need `if`, so they are plain text.
    runtime.append(
        e.let(
            "h_new_n",
            _text(
                e,
                "h_new",
                [e.s("o")],
                e.s("if (free_handles.length > 0) { const i = free_handles.pop(); handles[i] = o; return i; }"),
                e.s("const i = handles.length;"),
                e.s("handles.push(o);"),
                e.s("return i;"),
            ),
        )
    )
    runtime.append(
        e.let(
            "h_get_n",
            _text(
                e,
                "h_get",
                [e.s("h")],
                e.s(
                    'if (h >= handles.length || handles[h] === freed) throw new Error("webidl: handle " + h + " is not live");'
                ),
                e.s("return handles[h];"),
            ),
        )
    )
    runtime.append(
        e.let(
            "h_free_n",
            _text(
                e,
                "h_free",
                [e.s("h")],
                e.s(
                    'if (h >= handles.length || handles[h] === freed) throw new Error("webidl: handle " + h + " freed twice");'
                ),
                e.s("handles[h] = freed;"),
                e.s("free_handles.push(h);"),
            ),
        )
    )
    runtime.append(
        e.let(
            "str_n",
            _text(
                e,
                "str",
                [e.s("ptr"), e.s("len")],
                e.s("return decoder.decode(new Uint8Array(instance.exports.memory.buffer, ptr, len));"),
            ),
        )
    )
    runtime.append(
        e.ret(
            e.rec(
                e.p("h_new", e.v("h_new_n")),
                e.p("h_get", e.v("h_get_n")),
                e.p("h_free", e.v("h_free_n")),
                e.p("str", e.v("str_n")),
            )
        )
    )
    top.append(
        e.func_impl(
            e.v("runtime_b"),
            e.rec(e.p("mod", e.fld(e.v("js"), "mod_t"))),
            e.option_type_some(_rt_t(e)),
            e.mb.opt_none_type(),
            e.stage(e.mb.seq(runtime)),
        )
    )

    top.append(e.let("define_b", e.def_func(e.v("d"), "define")))
    define = []
    define.append(e.let("m", e.fld(e.v("arg"), "mod")))
    # `release` is not a spec member: it frees the handle table slot.
    define.append(
        e.if_only(
            e.eq(e.fld(e.v("arg"), "name"), e.s("release")),
            ret_m(e, _text(e, "wi_release", [e.s("h")], e.cat(_rt(e, "h_free"), e.s("(h);")))),
        )
    )
    define.append(
        e.let(
            "sig",
            e.call(
                e.lower(e.fld(e.v("webidl"), "sig_name")),
                e.rec(e.p("table", e.lower(e.fld(e.v("webidl"), "spec"))), e.p("name", e.fld(e.v("arg"), "name"))),
            ),
        )
    )
    define.append(e.if_only(e.not_(_sig(e, "ok")), e.mb.panic(e.cat(e.s("webidl-js: "), _sig(e, "err")))))
    define.append(e.let("kind", _sig(e, "kind")))
    define.append(e.let("member", _sig(e, "base")))
    define.append(e.let("params", e.list_new(e.mb.types_string())))
    define.append(e.let("lines", e.list_new(e.mb.types_string())))
    define.append(e.let("exprs", e.list_new(e.mb.types_string())))
    define.append(
        e.if_only(
            _sig(e, "self"),
            e.seq(_param(e, e.s("self")), _line(e, e.s("const recv = "), _rt(e, "h_get"), e.s("(self);"))),
        )
    )
    define.append(
        e.if_only(e.eq(e.v("kind"), e.s("ctor")), _line(e, e.s("const recv = globalThis."), _sig(e, "iface"), e.s(";")))
    )
    define.append(e.let("i", e.rec(e.p("v", e.int_of(0)))))
    define.append(
        e.foreach(
            _sig(e, "args"),
            "ap",
            e.seq(
                e.let("n", to_str(e, e.fld(e.v("i"), "v"))),
                e.incr(e.fld(e.v("i"), "v")),
                e.let("ak", e.call_m(e.v("ap"), "kind", e.tup())),
                e.let("optional", e.call_m(e.v("ap"), "optional", e.tup())),
                e.let("nullable", e.call_m(e.v("ap"), "nullable", e.tup())),
                e.if_only(e.v("optional"), _param(e, e.s("o"), e.v("n"))),
                e.if_only(e.v("nullable"), _param(e, e.s("n"), e.v("n"))),
                e.if_else(
                    _kind_is(e, e.v("ak"), "str", "buf"),
                    e.seq(_param(e, e.s("a"), e.v("n"), e.s("p")), _param(e, e.s("a"), e.v("n"), e.s("l"))),
                    _param(e, e.s("a"), e.v("n")),
                ),
                e.let("x", e.rec(e.p("v", e.dstr("")))),
                e.if_else(
                    _kind_is(e, e.v("ak"), "handle"),
                    e.mb.set(e.fld(e.v("x"), "v"), e.cat(_rt(e, "h_get"), e.s("(a"), e.v("n"), e.s(")"))),
                    e.if_else(
                        _kind_is(e, e.v("ak"), "str"),
                        e.mb.set(
                            e.fld(e.v("x"), "v"),
                            e.cat(_rt(e, "str"), e.s("(a"), e.v("n"), e.s("p, a"), e.v("n"), e.s("l)")),
                        ),
                        e.if_else(
                            _kind_is(e, e.v("ak"), "buf"),
                            e.mb.set(
                                e.fld(e.v("x"), "v"),
                                e.cat(
                                    e.s("new Uint8Array(instance.exports.memory.buffer, a"),
                                    e.v("n"),
                                    e.s("p, a"),
                                    e.v("n"),
                                    e.s("l)"),
                                ),
                            ),
                            e.if_else(
                                _kind_is(e, e.v("ak"), "bool"),
                                e.mb.set(e.fld(e.v("x"), "v"), e.cat(e.s("(a"), e.v("n"), e.s(" !== 0)"))),
                                e.if_else(
                                    _kind_is(e, e.v("ak"), "i64", "u64"),
                                    e.mb.set(e.fld(e.v("x"), "v"), e.cat(e.s("Number(a"), e.v("n"), e.s(")"))),
                                    e.mb.set(e.fld(e.v("x"), "v"), e.cat(e.s("a"), e.v("n"))),
                                ),
                            ),
                        ),
                    ),
                ),
                e.if_only(
                    e.v("nullable"),
                    e.mb.set(
                        e.fld(e.v("x"), "v"),
                        e.cat(e.s("(n"), e.v("n"), e.s(" !== 0 ? "), e.fld(e.v("x"), "v"), e.s(" : null)")),
                    ),
                ),
                e.if_only(
                    e.v("optional"),
                    e.mb.set(
                        e.fld(e.v("x"), "v"),
                        e.cat(e.s("(o"), e.v("n"), e.s(" !== 0 ? "), e.fld(e.v("x"), "v"), e.s(" : undefined)")),
                    ),
                ),
                e.push(e.v("exprs"), e.fld(e.v("x"), "v")),
            ),
        )
    )
    define.append(e.let("ret_out", _sig(e, "ret_out")))
    define.append(e.if_only(e.v("ret_out"), _param(e, e.s("out"))))
    define.append(e.let("argv", e.join(e.v("exprs"), ", ")))
    define.append(e.let("rk", _sig(e, "ret_kind")))
    define.append(
        e.if_else(
            e.eq(e.v("kind"), e.s("op")),
            # A void operation's call is a statement of its own: nothing to bind.
            _line(
                e,
                e.if_else(_kind_is(e, e.v("rk"), "void"), e.dstr(""), e.dstr("const r = ")),
                e.s("recv."),
                e.v("member"),
                e.s("("),
                e.v("argv"),
                e.s(");"),
            ),
            e.if_else(
                e.eq(e.v("kind"), e.s("get")),
                _line(e, e.s("const r = recv."), e.v("member"), e.s(";")),
                e.if_else(
                    e.eq(e.v("kind"), e.s("set")),
                    _line(e, e.s("recv."), e.v("member"), e.s(" = "), e.v("argv"), e.s(";")),
                    e.if_else(
                        e.eq(e.v("kind"), e.s("ctor")),
                        _line(e, e.s("const r = new recv("), e.v("argv"), e.s(");")),
                        e.if_else(
                            e.eq(e.v("kind"), e.s("callback")),
                            _line(
                                e,
                                e.s("const r = function() { return instance.exports["),
                                e.v("argv"),
                                e.s("].apply(null, arguments); };"),
                            ),
                            _line(e, e.s("const r = globalThis;")),
                        ),
                    ),
                ),
            ),
        )
    )
    define.append(e.let("rx", e.rec(e.p("v", e.dstr("")))))
    define.append(
        e.if_else(
            _kind_is(e, e.v("rk"), "handle", "str"),
            e.mb.set(e.fld(e.v("rx"), "v"), e.cat(_rt(e, "h_new"), e.s("(r)"))),
            e.if_else(
                _kind_is(e, e.v("rk"), "bool"),
                e.mb.set(e.fld(e.v("rx"), "v"), e.dstr("(r ? 1 : 0)")),
                e.if_else(
                    _kind_is(e, e.v("rk"), "i64", "u64"),
                    e.mb.set(e.fld(e.v("rx"), "v"), e.dstr("BigInt(r)")),
                    e.if_else(
                        _kind_is(e, e.v("rk"), "void"),
                        e.mb.set(e.fld(e.v("rx"), "v"), e.dstr("")),
                        e.mb.set(e.fld(e.v("rx"), "v"), e.dstr("r")),
                    ),
                ),
            ),
        )
    )
    define.append(
        e.if_else(
            e.v("ret_out"),
            e.seq(
                e.if_only(
                    _kind_is(e, e.v("rk"), "i64", "u64", "f32", "f64"),
                    e.mb.panic(
                        e.cat(
                            e.s("webidl-js: nullable return of kind "),
                            e.v("rk"),
                            e.s(" is not supported: "),
                            e.fld(e.v("arg"), "name"),
                        )
                    ),
                ),
                _line(e, e.s("const cell = new Uint32Array(instance.exports.memory.buffer, out, 2);")),
                _line(e, e.s("if (r === null || r === undefined) {")),
                _line(e, e.s("  cell[0] = 0;")),
                _line(e, e.s("} else {")),
                _line(e, e.s("  cell[0] = 1;")),
                _line(e, e.s("  cell[1] = "), e.fld(e.v("rx"), "v"), e.s(";")),
                _line(e, e.s("}")),
            ),
            e.if_only(
                e.not_(e.eq(e.fld(e.v("rx"), "v"), e.s(""))), _line(e, e.s("return "), e.fld(e.v("rx"), "v"), e.s(";"))
            ),
        )
    )
    define.append(
        e.ret(
            e.call_m(
                e.v("m"),
                "func_text",
                e.rec(
                    e.p("name", e.cat(e.s("wi_"), e.fld(e.v("arg"), "name"))),
                    e.p("params", e.v("params")),
                    e.p("lines", e.v("lines")),
                ),
            )
        )
    )
    top.append(
        e.func_impl(
            e.v("define_b"),
            e.rec(e.p("mod", e.fld(e.v("js"), "mod_t")), e.p("name", e.mb.types_string()), e.p("rt", _rt_t(e))),
            e.option_type_some(e.mb.types_string()),
            e.mb.opt_none_type(),
            e.stage(body(e, *define)),
        )
    )
    top.append(e.finish(e.v("d")))
    top.append(
        e.ret(e.rec(e.p("runtime", e.fld(e.v("runtime_b"), "func")), e.p("define", e.fld(e.v("define_b"), "func"))))
    )
    return top
