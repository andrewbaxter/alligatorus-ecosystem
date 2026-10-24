"""The editor protocol around an editor's own code (merman-editor.atz): an `App` makes the wat module, imports
merman's host functions and the component libraries, and defines the exports merman calls, wired to a document
store (editor-state.atz).

The app's state is one owned record (record-wasm.atz) in the module's one global cell: `st` (the store), `root`
(the pane's element, owned), `running`, `frame` (the frame closure, owned) and `frame_id`, then the editor's own
fields (`fields`: owned component records, widgets, plain values); `app.g(name)` is a field's place, read through
the cell. `_start(root)` sets up editor-ui.atz in the pane's element, makes the store, runs the editor's `start`
statements (seeing `root`, an owned `Element`, and `st`), makes the record from the editor's field values, opens the
document and requests the first frame; `stop` runs the editor's `stop` code, cancels the pending frame and drops the
record (every listener, element, closure and component with it, the store last); `on_doc` loads the document and
`on_level` applies an undo level, then run the editor's `sync` code (which reads the store's changed lists);
`doc_ptr`/`doc_len` are
the serialized document; `alloc` hands merman zeroed memory (freed after the store copied what was delivered);
`on_fs(req, status, ptr, len)` runs the editor's `fs` code. The record drops its fields in their order, so a
listener comes before the element it is on (its drop removes it from the element), and a component before what it
borrows.

Event handlers (`app.event(name, body)`) and the frame (`app.frame(body)`) are closures without captures
(closure-wasm.atz; editor-ui.atz's `ev_cb`, whose `call` takes the owned event, and `frame_cb`): `app.cb(name)` is
a handler's callable (raw), for the controls; `app.callback(name, body)` + `app.handler(name)` give a component an
owned closure of its own. A component taking a child interface (iface-wasm.atz; editor-canvas.atz's `cv_child`) gets
the app's implementation: `app.implement(name, iface, own, methods)` defines one dependency per method over the
app's cell handle (`app_ref_t`: the module's cell as an owned handle, whose destroy is nothing, the cell being
static) and `app.child(name)` (staged) is the owned interface value over it. Staged code reaches the store as
`app.st()` and commits a change with `app.commit()` (an undo level when anything changed). Module-level texts
(`app.text(name, text)`) are `str` values in staged code (`app.s(name)`) or (address, length) pairs (`app.t(name)`);
`app.let(name, expr)` binds another module-level constant the staged code lowers.

Levels: the types (one), the libraries' types and the app record (two), the host imports, the cell, the texts,
the closures and the method dependencies (three), then the interface implementations and the exports (the module's
top)."""

from ..collections import closure_wasm, iface_wasm, record_wasm
from ..eco_mb import p
from ..memory import destructor
from ..merman.merman_editor import FILE as EDITOR_FILE
from ..target_mb import fn_of
from . import editor_json, editor_mem, editor_state, editor_types, editor_ui
from ..wasm import math_wasm
from ..wasm.kit import Kit, as_seq

HOST = ["doc_open", "doc_edit", "fs_read", "fs_write", "log"]

LIBS = [
    ("math", math_wasm.FILE),
    ("mem", editor_mem.FILE),
    ("json", editor_json.FILE),
    ("state", editor_state.FILE),
    ("ui", editor_ui.FILE),
    ("types", editor_types.FILE),
]

FN_TYPES = {
    "fn_void_t": ([], "t_void"),
    "fn_alloc_t": (["t_i32"], "t_i32"),
    "fn_ret_i32_t": ([], "t_i32"),
    "fn_doc_t": (["t_i32", "t_i32"], "t_void"),
    "fn_level_t": (["t_i32", "t_i32", "t_i32"], "t_void"),
    "fn_fs_t": (["t_i32", "t_i32", "t_i32", "t_i32"], "t_void"),
}

# The editor-ui and editor-types names the app and its code bind by name.
UI_TYPES = editor_ui.TYPE_EXPORTS + ["t_pu8"]
TYPES_NAMES = [n for n in editor_types.EXPORTS if n not in UI_TYPES]
# The record's own fields before the editor's: the root element, the running flag, the frame closure and request;
# the handlers follow the editor's fields (whose listeners borrow them), and the store comes last (the components
# borrow it).
OWN_FIELDS = [
    ("root", "el_t"),
    ("running", "t_i32"),
    ("frame", "frame_cb_t"),
    ("frame_id", "t_i32"),
]
STORE_FIELD = ("st", "state.st_t")


class App:
    def __init__(self, e, doc_name, doc_key, libs, fields):
        """`libs`: further (binding, file) imports; `fields`: the editor's record fields, a list of (name, type)
        where the type is a binding name at the record's level (`t_i32`, `t_f64`, an editor-ui type, or a type an
        imported library exports as `<lib>.<name>`, written `"lib.name"`)."""
        self.e = e
        self.k = Kit(e)
        self.doc_name = doc_name
        self.doc_key = doc_key
        self.texts = {}
        self.fields = list(fields)
        self.has_frame = False
        self.handlers = []
        self.pre = []
        self.top_names = []
        self.impls = []
        self.libs = LIBS + list(libs)
        k = self.k
        # Level one: the module, the types, the host functions' types.
        setup = []
        k.bind(setup)
        setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
        setup.append(e.let("t_pv", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_void"))))
        setup.append(e.let("editor", e.import_local("editor", EDITOR_FILE)))
        for name, (params, ret) in FN_TYPES.items():
            setup.append(e.let(name, k.fn_t(params, ret)))
        for name in HOST:
            setup.append(e.let(name + "_t", e.call_m(e.fld(e.v("editor"), "fn_types"), "get", e.s(name))))
        # the cell handle's destroy: the cell is static
        k.dep(setup, "app_ref_destroy", ["r"], ["t_pv"], "t_void", e.seq())
        self.exported = (
            ["m", "t_void", "t_i32", "t_u8", "t_u32", "t_f32", "t_f64", "t_pv", "t_pu8", "t_pi32", "t_pf64", "t_pf32"]
            + list(FN_TYPES)
            + [n + "_t" for n in HOST]
            + ["app_ref_destroy"]
        )
        setup.append(e.ret(e.rec(*[p(n, e.v(n)) for n in self.exported])))
        # Level two: the libraries' types and the app record.
        mid = []
        mid.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
        mid.append(e.let("k", e.lower(e.mb.seq(setup))))
        for n in self.exported:
            mid.append(e.let(n, e.fld(e.v("k"), n)))
        mid.append(e.let("record", e.import_local("record", record_wasm.FILE)))
        mid.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
        for name, file in self.libs:
            mid.append(e.let(name, e.import_local(name, file)))
        for n in UI_TYPES:
            mid.append(e.let(n, e.fld(e.v("ui"), n)))
        for n in TYPES_NAMES:
            mid.append(e.let(n, e.fld(e.v("types"), n)))
        # `_start` takes the pane's element owned.
        mid.append(e.let("fn_start_t", k.fn_t(["el_t"], "t_void")))
        # the cell handle: what the app's interface implementations are over
        mid.append(
            e.let(
                "app_ref_r",
                e.call(
                    e.fld(e.v("destructor"), "type"),
                    e.rec(p("under", e.v("t_pv")), p("destroy", e.v("app_ref_destroy"))),
                ),
            )
        )
        mid.append(e.let("app_ref_t", e.fld(e.v("app_ref_r"), "type")))
        self.mid = mid
        self.text("app_doc_name", doc_name)
        self.text("app_doc_key", doc_key)

    def _type(self, ty):
        """A type by its binding name at the level it is used (`t_i32`, an editor-ui type, or `lib.name`)."""
        e = self.e
        if "." in ty:
            lib, name = ty.split(".", 1)
            return e.fld(e.v(lib), name)
        return e.v(ty)

    def _module(self):
        """Level three: level two lowered with the app record (whose fields are known once the handlers are), the
        host imports, the app cell and the editor's own module-level statements (`pre`)."""
        e = self.e
        mid = self.mid
        field_type = self._type
        record_fields = OWN_FIELDS + self.fields + [(name + "_h", "ev_cb_t") for name in self.handlers] + [STORE_FIELD]
        mid.append(
            e.let(
                "app_r",
                e.call(
                    e.fld(e.v("record"), "type"),
                    e.rec(p("fields", e.rec(*[p(name, field_type(ty)) for name, ty in record_fields]))),
                ),
            )
        )
        for f in ["t", "own", "raw", "new"]:
            mid.append(e.let("app_" + f, e.fld(e.v("app_r"), "type" if f == "t" else f)))
        mid_exported = (
            self.exported
            + UI_TYPES
            + TYPES_NAMES
            + ["fn_start_t", "app_t", "app_own", "app_raw", "app_new", "app_ref_t"]
        )
        mid.append(e.ret(e.rec(*[p(n, e.v(n)) for n in mid_exported])))
        top = []
        top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
        top.append(e.let("editor", e.import_local("editor", EDITOR_FILE)))
        top.append(e.let("closure", e.import_local("closure", closure_wasm.FILE)))
        for name, file in self.libs:
            top.append(e.let(name, e.import_local(name, file)))
        top.append(e.let("k2", e.lower(e.mb.seq(mid))))
        for n in mid_exported:
            top.append(e.let(n, e.fld(e.v("k2"), n)))
        self.top_names = mid_exported + HOST + ["app_cell"] + self.top_names
        for name in HOST:
            top.append(
                e.let(
                    name,
                    e.call(
                        e.fld(e.v("wasm"), "import_fn"),
                        e.rec(
                            p("module", e.fld(e.v("editor"), "module")), p("name", e.s(name)), p("ty", e.v(name + "_t"))
                        ),
                    ),
                )
            )
        # the one global: the app record's pointer
        top.append(
            e.let(
                "app_cell",
                e.call(
                    e.fld(e.v("wasm"), "alloc_fn"),
                    e.rec(p("mod", e.v("m")), p("name", e.s("app_cell")), p("size", e.n(4))),
                ),
            )
        )
        return top + self.pre

    # --- module level ---

    def text(self, name, text):
        """A module-level text constant `name`."""
        e = self.e
        if name in self.texts:
            assert self.texts[name] == text, name
            return
        self.texts[name] = text
        self.let(name, e.call_m(e.v("m"), "cstr", e.s(text)))

    def let(self, name, expr):
        """A module-level constant `name` (level three) the staged code lowers."""
        self.top_names.append(name)
        self.pre.append(self.e.let(name, expr))

    def implement(self, name, iface, own, methods):
        """The app's implementation `name` of the interface `iface` (its declared type and `own` its owned type,
        `lib.name` bindings): `methods` lists (method, parameter name, parameter type, body) for every method
        (results void); each is a dependency `<name>_<method>(self, param)` over the cell handle, its body seeing
        the parameter under its name. `child(name)` is the owned interface value."""
        for method, param, param_type, body_ in methods:
            self.k.dep(self.pre, name + "_" + method, ["self", param], ["t_pv", param_type], "t_void", body_)
            self.top_names.append(name + "_" + method)
        self.impls.append((name, iface, own, [m for m, *_ in methods]))

    def export(self, name, params, fn_type, body_):
        """An export `name` (parameter names, a FN_TYPES name); its body is labeled `fn` (kit.ret)."""
        e = self.e
        self.fin.append(
            e.call(
                e.fld(e.v("wasm"), "export_fn"),
                e.rec(
                    p("mod", e.v("m")),
                    p("name", e.s(name)),
                    p("params", e.tup(*[e.s(pn) for pn in params])),
                    p("ty", e.v(fn_type)),
                    p("body", e.stage(as_seq(e, body_))),
                ),
            )
        )

    def closure(self, name, callable_t, param, body_, owned):
        """A closure `name` without captures of the signature `callable_t`, its body seeing the argument as
        `param` (moved into it when `owned`; labeled `fn`: kit.ret); `cb(name)` is its callable.
        """
        e = self.e
        arg = self.k.m(e.v("arg"), "move", e.tup()) if owned else e.v("arg")
        self.top_names.append(name + "_cb")
        self.pre.append(
            e.let(
                name + "_cb",
                e.fld(
                    e.call(
                        e.fld(e.v("closure"), "new"),
                        e.rec(
                            p("callable", e.v(callable_t)),
                            p("capture", e.rec()),
                            p("body", e.stage(e.seq(e.let(param, arg), as_seq(e, body_)))),
                        ),
                    ),
                    "make",
                ),
            )
        )

    def event(self, name, body_):
        """A handler `name` a control calls with the owned event (released when the handler returns), which `body_`
        sees as `ev` (its reference: an `Event` raw handle). The app record owns the handler's closure (made in
        `_start`, where `cb(name)` is its binding)."""
        self.handlers.append(name)
        self.closure(name, "ev_cb_t", "ev", body_, True)

    def callback(self, name, body_):
        """A handler `name` like `event`'s, but not kept by the app: `handler(name)` makes a fresh owned closure of
        it each time, for a component that owns the callable it is given."""
        self.closure(name, "ev_cb_t", "ev", body_, True)

    def handler(self, name):
        """A fresh owned closure of the callback `name` (`callback`), to give to a component."""
        e = self.e
        return e.call(fn_of(e, self.k.lo(name + "_cb")), e.rec())

    def frame(self, body_):
        """The handler `frame(time)` run every animation frame from `_start` until `stop` (the frame after `stop`
        does nothing and asks for no other)."""
        e = self.e
        k = self.k
        self.has_frame = True
        self.closure(
            "frame",
            "frame_cb_t",
            "time",
            e.seq(
                k.if_(k.eq(self.g("running"), e.n(0)), k.ret()),
                body_,
                k.set(self.g("frame_id"), self.ui("frame", self.g("frame"))),
            ),
            False,
        )

    def finish(self, start, fields, sync, fs, stop):
        """Defines the protocol's exports around the editor's code and returns the module's top level: `start`
        (statements seeing `root`, the owned `Element` binding `_start` received, `st` and the handlers' bindings)
        runs before the record is made from `fields` (name → value, owned ones moved: `v.move()`), then the
        document opens and the first frame runs; `sync` and `fs` (seeing `req`, `status`, `ptr`, `len`) as the
        protocol says; `stop` runs before the record is dropped."""
        e = self.e
        k = self.k
        v = e.v
        assert self.has_frame, "an app has a frame (app.frame)"
        top = self._module()
        top.append(e.ret(e.rec(*[p(n, v(n)) for n in self.top_names])))
        # the module's top: the interface implementations over level three, then the exports
        fin = []
        fin.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
        fin.append(e.let("editor", e.import_local("editor", EDITOR_FILE)))
        fin.append(e.let("iface", e.import_local("iface", iface_wasm.FILE)))
        for name, file in self.libs:
            fin.append(e.let(name, e.import_local(name, file)))
        fin.append(e.let("k3", e.lower(e.mb.seq(top))))
        for n in self.top_names:
            fin.append(e.let(n, e.fld(v("k3"), n)))
        for name, iface, _, methods in self.impls:
            fin.append(
                e.let(
                    name + "_up",
                    e.fld(
                        e.call(
                            e.fld(v("iface"), "impl"),
                            e.rec(
                                p("iface", self._type(iface)),
                                p("self", v("app_ref_t")),
                                p("methods", e.rec(*[p(m, v(name + "_" + m)) for m in methods])),
                            ),
                        ),
                        "upcast",
                    ),
                )
            )
        self.fin = fin
        own_values = [
            p("st", k.m(v("st"), "move", e.tup())),
            p("root", k.m(v("root"), "move", e.tup())),
            p("running", k.i32(1)),
            p("frame", k.m(v("frame_v"), "move", e.tup())),
            p("frame_id", k.i32(0)),
            *[p(name + "_h", k.m(v(name + "_h"), "move", e.tup())) for name in self.handlers],
        ]
        self.export(
            "_start",
            ["r"],
            "fn_start_t",
            e.seq(
                e.let("root", k.m(v("r"), "move", e.tup())),
                self.ui("init", v("root")),
                e.let("st", k.lib("state", "st_new")),
                e.let("frame_v", e.call(fn_of(e, k.lo("frame_cb")), e.rec())),
                *[e.let(name + "_h", e.call(fn_of(e, k.lo(name + "_cb")), e.rec())) for name in self.handlers],
                # the editor's statements, in this scope: their bindings are the record's field values
                *(start["variant"]["seq"] if "seq" in start["variant"] else [start]),
                e.let(
                    "a",
                    k.call("app_new", e.rec(*own_values, *[p(name, value) for name, value in fields.items()])),
                ),
                k.set(self.cell(), k.addr(k.m(v("a"), "forget", e.tup()))),
                k.call("doc_open", *self.ts("app_doc_name"), *self.ts("app_doc_key")),
                k.set(self.g("frame_id"), self.ui("frame", self.g("frame"))),
            ),
        )
        self.export(
            "stop",
            [],
            "fn_void_t",
            e.seq(
                k.set(self.g("running"), e.n(0)),
                stop,
                self.ui("cancel_frame", self.g("frame_id")),
                e.seq(e.let("a", e.mb.as_(self.app(), k.lo("app_own")))),
                k.set(self.cell(), e.n(0)),
            ),
        )
        self.export("alloc", ["n"], "fn_alloc_t", e.ret(k.lib("mem", "mem_alloc", v("n"))))
        self.export("doc_ptr", [], "fn_ret_i32_t", e.ret(k.addr(e.fld(k.lib("state", "st_doc", self.st()), "data"))))
        self.export("doc_len", [], "fn_ret_i32_t", e.ret(e.fld(k.lib("state", "st_doc", self.st()), "len")))
        self.export(
            "on_doc",
            ["ptr", "len"],
            "fn_doc_t",
            e.seq(
                k.lib("state", "st_load", self.st(), k.str_of(k.ptr_of(v("ptr"), "t_pu8"), v("len"))),
                k.lib("mem", "mem_free", v("ptr")),
                sync,
            ),
        )
        self.export(
            "on_level",
            ["ptr", "len", "redo"],
            "fn_level_t",
            e.seq(
                k.lib("state", "st_level", self.st(), k.str_of(k.ptr_of(v("ptr"), "t_pu8"), v("len")), v("redo")),
                k.lib("mem", "mem_free", v("ptr")),
                sync,
            ),
        )
        self.export(
            "on_fs",
            ["req", "status", "ptr", "len"],
            "fn_fs_t",
            e.seq(fs, k.if_(k.ne(v("ptr"), e.n(0)), k.lib("mem", "mem_free", v("ptr")))),
        )
        self.fin.append(e.ret(e.call(e.fld(e.v("editor"), "build"), e.call_m0(e.v("m"), "render"))))
        return self.fin

    # --- staged ---

    def cell(self):
        """The global cell's place (the app record's pointer as an i32)."""
        k = self.k
        return k.at(k.addr(k.lo("app_cell")), 0)

    def app(self):
        """The app record (raw)."""
        e = self.e
        return e.mb.as_(self.k.ptr_of(self.cell(), "t_pv"), self.k.lo("app_raw"))

    def g(self, name):
        """A field of the app record (`fields`, plus the record's own)."""
        return self.e.fld(self.app(), name)

    def st(self):
        return self.g("st")

    def cb(self, name):
        """The handler `name`'s callable: its binding in `_start` (the app record's from then on), a borrow where a
        control takes it."""
        return self.e.v(name + "_h")

    def child(self, name):
        """The owned interface value of the implementation `name` (`implement`) over the app's cell handle, for the
        component taking it."""
        e = self.e
        k = self.k
        own = [own for n, _, own, _ in self.impls if n == name]
        assert len(own) == 1, name
        return e.mb.as_(k.dcall(name + "_up", k.ptr_of(k.addr(k.lo("app_cell")), "t_pv")), e.lower(self._type(own[0])))

    def s(self, name):
        """The text `name` as a `str` value."""
        k = self.k
        return k.str_of(k.ptr_of(k.addr(k.lo(name)), "t_pu8"), k.i32(len(self.texts[name].encode())))

    def t(self, name):
        """The text `name` as (address, length) i32 values."""
        return [self.k.addr(self.k.lo(name)), self.e.n(len(self.texts[name].encode()))]

    def ts(self, name):
        """The text `name` as (ptr(u8), i32) host-import arguments."""
        return [self.k.lo(name), self.e.n(len(self.texts[name].encode()))]

    def ui(self, f, *args):
        return self.k.lib("ui", f, *args)

    def commit(self):
        """Commits the store's changes: an undo level for merman when anything changed."""
        e = self.e
        k = self.k
        v = e.v
        return k.if_(
            k.ne(k.lib("state", "st_commit", self.st()), e.n(0)),
            e.let("level", k.lib("state", "st_level_text", self.st())),
            k.call("doc_edit", e.fld(v("level"), "data"), e.fld(v("level"), "len")),
        )
