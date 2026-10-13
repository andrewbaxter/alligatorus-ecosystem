"""wasm-alloc.atz: a heap for wasm modules (browser-safe: no WASI). Exports `{malloc, free}`.

A dlmalloc-style allocator. Chunks are 8-byte aligned with an 8-byte overhead: `prev_foot` (the previous chunk's size,
meaningful only when that chunk is free) at +0 and `head` at +4, which is the chunk size with two flag bits: bit 0
(the previous chunk is in use) and bit 1 (this chunk is in use). The payload starts at +8; a free chunk keeps its
free-list links `fd`/`bk` there, so the smallest chunk is 16 bytes, and a chunk needing `n` payload bytes is
`align8(n + 4)` (an in-use chunk's last 4 bytes double as the next chunk's `prev_foot`).

Free chunks sit in 80 bins of doubly linked lists: exact bins for sizes below 256 (one per 8 bytes), then two bins per
power of two above. `malloc` takes the first fitting chunk from the smallest bin that has one, splitting off a
remainder of at least 16 bytes; otherwise it carves from the top chunk, which starts at the first page boundary after
the static data and grows with `memory.grow` (yielding 0 when that fails). `free` coalesces with free neighbours
through the boundary tags, merges into the top chunk when adjacent to it, and bins the result; `free(0)` is a no-op.

Everything is a dependency (`func_dep`/`alloc_dep`): a module that calls `malloc` or `free` gets the functions and the
state block on first use; nothing is passed around.
"""

from ..eco_mb import p

FILE = "wasm-alloc.atz"

PAGE = 65536
OVERHEAD = 8
MIN_CHUNK = 16
SMALL_LIMIT = 256
SMALL_BINS = SMALL_LIMIT // 8  # indices 2..31 used
LARGE_BIN_BITS = list(range(8, 32))  # a size in [2^k, 2^(k+1)) takes two bins
BIN_COUNT = SMALL_BINS + 2 * len(LARGE_BIN_BITS)
STATE_TOP = 0
STATE_TOP_SIZE = 1
STATE_BINS = 2
STATE_SIZE = 4 * (STATE_BINS + BIN_COUNT)
PINUSE = 1
CINUSE = 2


def _ty(e, name):
    return e.lower(e.v(name))


def _i32(e, v):
    return e.mb.as_(v, _ty(e, "t_i32"))


def _pv(e, v):
    return e.mb.as_(v, _ty(e, "t_pv"))


def _i32p(e, addr):
    return e.mb.as_(addr, _ty(e, "t_pi32"))


def _cell(e, addr, index):
    """The i32 cell `index` (4 bytes each) at address `addr` (i32)."""
    return e.mb.field(_i32p(e, addr), e.n(index))


def _state(e, index):
    """A cell of the state block: 0 top, 1 top size, then the bin heads."""
    return e.mb.field(_i32p(e, e.call(e.lower(e.v("state")), e.tup())), e.n(index))


def _bin(e, idx):
    return e.mb.field(_i32p(e, e.call(e.lower(e.v("state")), e.tup())), e.mb.operator_add(idx, e.n(STATE_BINS)))


def _hook(e, name):
    """A wat intrinsic made where it is used: only its TYPE is lowered into the body."""
    return e.call(e.lower(e.fld(e.v("wasm"), name)), e.rec())


def _dep(e, name, arg):
    return e.call(e.lower(e.v(name)), arg)


# Chunk fields (the chunk address is an i32).
def _prev_foot(e, c):
    return _cell(e, c, 0)


def _head(e, c):
    return _cell(e, c, 1)


def _fd(e, c):
    return _cell(e, c, 2)


def _bk(e, c):
    return _cell(e, c, 3)


def _size_of(e, c):
    return e.mb.operator_and(_head(e, c), e.n(-8))


def _flag(e, c, bit):
    return e.not_(e.eq(e.mb.operator_and(_head(e, c), e.n(bit)), e.n(0)))


def _binidx_body(e):
    """binidx(s): the bin for a chunk of size s (a multiple of 8, at least 16)."""
    out = [
        e.if_only(
            e.mb.operator_lt(e.v("s"), e.n(SMALL_LIMIT)), e.mb.return_to("fn", e.mb.operator_ushr(e.v("s"), e.n(3)))
        )
    ]
    for i, k in enumerate(LARGE_BIN_BITS):
        # sizes in [2^k, 2^(k+1)): the bit below the top one picks the half
        half = e.mb.operator_and(e.mb.operator_ushr(e.v("s"), e.n(k - 1)), e.n(1))
        idx = e.mb.operator_add(half, e.n(SMALL_BINS + 2 * i))
        if k == LARGE_BIN_BITS[-1]:
            out.append(e.mb.return_to("fn", idx))
        else:
            out.append(
                e.if_only(e.mb.operator_lt(e.mb.operator_ushr(e.v("s"), e.n(k + 1)), e.n(1)), e.mb.return_to("fn", idx))
            )
    return e.mb.labeled("fn", e.seq(*out))


def _insert_body(e):
    """insert(c): puts the free chunk c (its head holds its size) at the front of its bin."""
    c = e.v("c")
    return e.seq(
        e.let("idx", _dep(e, "binidx", _size_of(e, c))),
        e.let("first", _bin(e, e.v("idx"))),
        e.mb.set(_fd(e, c), e.v("first")),
        e.mb.set(_bk(e, c), _i32(e, e.n(0))),
        e.if_only(e.not_(e.eq(e.v("first"), e.n(0))), e.mb.set(_bk(e, e.v("first")), c)),
        e.mb.set(_bin(e, e.v("idx")), c),
    )


def _unlink_body(e):
    """unlink(c): takes the free chunk c out of its bin."""
    c = e.v("c")
    return e.seq(
        e.let("f", _fd(e, c)),
        e.let("b", _bk(e, c)),
        e.if_else(
            e.eq(e.v("b"), e.n(0)),
            e.mb.set(_bin(e, _dep(e, "binidx", _size_of(e, c))), e.v("f")),
            e.mb.set(_fd(e, e.v("b")), e.v("f")),
        ),
        e.if_only(e.not_(e.eq(e.v("f"), e.n(0))), e.mb.set(_bk(e, e.v("f")), e.v("b"))),
    )


def _malloc_body(e):
    # The search block yields a fitting free chunk's address, or 0.
    scan = e.seq(
        e.if_only(e.eq(e.v("cur"), e.n(0)), e.mb.return_label("scan")),
        e.if_only(e.mb.operator_ge(_size_of(e, e.v("cur")), e.v("req")), e.mb.return_to("search", e.v("cur"))),
        e.mb.set(e.v("cur"), _fd(e, e.v("cur"))),
    )
    bins = e.seq(
        e.if_only(e.mb.operator_ge(e.v("idx"), e.n(BIN_COUNT)), e.mb.return_to("search", _i32(e, e.n(0)))),
        e.let("cur", _bin(e, e.v("idx"))),
        e.mb.labeled("scan", e.foreach(_hook(e, "loop_fn"), "_", scan)),
        e.mb.set(e.v("idx"), e.mb.operator_add(e.v("idx"), e.n(1))),
    )
    search = e.mb.labeled(
        "search",
        e.seq(
            e.let("idx", _dep(e, "binidx", e.v("req"))),
            e.foreach(_hook(e, "loop_fn"), "_", bins),
            e.mb.return_to("search", _i32(e, e.n(0))),
        ),
    )
    found = e.v("found")
    use_found = e.seq(
        _dep(e, "unlink", found),
        e.let("rest", e.mb.operator_sub(_size_of(e, found), e.v("req"))),
        e.if_else(
            e.mb.operator_ge(e.v("rest"), e.n(MIN_CHUNK)),
            e.seq(
                # split: the remainder is a free chunk whose previous chunk (found) is in use
                e.let("r", e.mb.operator_add(found, e.v("req"))),
                e.mb.set(
                    _head(e, found),
                    e.mb.operator_or(
                        e.mb.operator_and(_head(e, found), e.n(PINUSE)), e.mb.operator_or(e.v("req"), e.n(CINUSE))
                    ),
                ),
                e.mb.set(_head(e, e.v("r")), e.mb.operator_or(e.v("rest"), e.n(PINUSE))),
                e.mb.set(_prev_foot(e, e.mb.operator_add(e.v("r"), e.v("rest"))), e.v("rest")),
                _dep(e, "insert", e.v("r")),
            ),
            e.seq(
                e.mb.set(_head(e, found), e.mb.operator_or(_head(e, found), e.n(CINUSE))),
                e.let("nx", e.mb.operator_add(found, _size_of(e, found))),
                e.mb.set(_head(e, e.v("nx")), e.mb.operator_or(_head(e, e.v("nx")), e.n(PINUSE))),
            ),
        ),
        e.mb.return_to("fn", _pv(e, e.mb.operator_add(found, e.n(OVERHEAD)))),
    )
    grow = e.seq(
        e.let(
            "pages",
            e.mb.operator_div(
                e.mb.operator_add(e.mb.operator_sub(e.v("req"), _state(e, STATE_TOP_SIZE)), e.n(PAGE - 1)), e.n(PAGE)
            ),
        ),
        e.let("grown", e.call(_hook(e, "memory_grow_fn"), e.v("pages"))),
        e.if_only(e.eq(e.v("grown"), e.n(-1)), e.mb.return_to("fn", _pv(e, e.n(0)))),
        e.mb.set(
            _state(e, STATE_TOP_SIZE),
            e.mb.operator_add(_state(e, STATE_TOP_SIZE), e.mb.operator_mul(e.v("pages"), e.n(PAGE))),
        ),
    )
    return e.mb.labeled(
        "fn",
        e.seq(
            e.let("n1", e.if_else(e.eq(e.v("n"), e.n(0)), _i32(e, e.n(1)), e.v("n"))),
            e.let(
                "req0", e.mb.operator_mul(e.mb.operator_div(e.mb.operator_add(e.v("n1"), e.n(4 + 7)), e.n(8)), e.n(8))
            ),
            e.let(
                "req", e.if_else(e.mb.operator_lt(e.v("req0"), e.n(MIN_CHUNK)), _i32(e, e.n(MIN_CHUNK)), e.v("req0"))
            ),
            e.let("found", search),
            e.if_only(e.not_(e.eq(e.v("found"), e.n(0))), use_found),
            # from the top chunk, which starts at the first page boundary after the static data
            e.if_only(
                e.eq(_state(e, STATE_TOP), e.n(0)),
                e.mb.set(
                    _state(e, STATE_TOP), e.mb.operator_mul(e.call(_hook(e, "memory_size_fn"), e.tup()), e.n(PAGE))
                ),
            ),
            e.if_only(e.mb.operator_gt(e.v("req"), _state(e, STATE_TOP_SIZE)), grow),
            e.let("c", _state(e, STATE_TOP)),
            e.mb.set(_head(e, e.v("c")), e.mb.operator_or(e.v("req"), e.n(PINUSE | CINUSE))),
            e.mb.set(_state(e, STATE_TOP), e.mb.operator_add(e.v("c"), e.v("req"))),
            e.mb.set(_state(e, STATE_TOP_SIZE), e.mb.operator_sub(_state(e, STATE_TOP_SIZE), e.v("req"))),
            # the top chunk's own head: free, previous in use (the carved chunk)
            e.if_only(
                e.mb.operator_gt(_state(e, STATE_TOP_SIZE), e.n(0)),
                e.mb.set(_head(e, _state(e, STATE_TOP)), e.mb.operator_or(_state(e, STATE_TOP_SIZE), e.n(PINUSE))),
            ),
            e.mb.return_to("fn", _pv(e, e.mb.operator_add(e.v("c"), e.n(OVERHEAD)))),
        ),
    )


def _free_body(e):
    return e.mb.labeled(
        "fn",
        e.seq(
            e.let("addr", _i32(e, e.v("p"))),
            e.if_only(e.eq(e.v("addr"), e.n(0)), e.mb.return_label("fn")),
            e.let("c", e.mb.operator_sub(e.v("addr"), e.n(OVERHEAD))),
            e.let("s", _size_of(e, e.v("c"))),
            # coalesce backward
            e.if_only(
                e.not_(_flag(e, e.v("c"), PINUSE)),
                e.seq(
                    e.let("ps", _prev_foot(e, e.v("c"))),
                    e.mb.set(e.v("c"), e.mb.operator_sub(e.v("c"), e.v("ps"))),
                    _dep(e, "unlink", e.v("c")),
                    e.mb.set(e.v("s"), e.mb.operator_add(e.v("s"), e.v("ps"))),
                ),
            ),
            e.let("nx", e.mb.operator_add(e.v("c"), e.v("s"))),
            # adjacent to the top chunk: merge into it
            e.if_only(
                e.eq(e.v("nx"), _state(e, STATE_TOP)),
                e.seq(
                    e.mb.set(_state(e, STATE_TOP), e.v("c")),
                    e.mb.set(_state(e, STATE_TOP_SIZE), e.mb.operator_add(_state(e, STATE_TOP_SIZE), e.v("s"))),
                    e.mb.set(_head(e, e.v("c")), e.mb.operator_or(_state(e, STATE_TOP_SIZE), e.n(PINUSE))),
                    e.mb.return_label("fn"),
                ),
            ),
            # coalesce forward
            e.if_only(
                e.not_(_flag(e, e.v("nx"), CINUSE)),
                e.seq(
                    e.let("ns", _size_of(e, e.v("nx"))),
                    _dep(e, "unlink", e.v("nx")),
                    e.mb.set(e.v("s"), e.mb.operator_add(e.v("s"), e.v("ns"))),
                    e.mb.set(e.v("nx"), e.mb.operator_add(e.v("c"), e.v("s"))),
                ),
            ),
            e.mb.set(_head(e, e.v("c")), e.mb.operator_or(e.v("s"), e.n(PINUSE))),
            e.mb.set(_prev_foot(e, e.v("nx")), e.v("s")),
            e.mb.set(_head(e, e.v("nx")), e.mb.operator_and(_head(e, e.v("nx")), e.n(-2))),
            _dep(e, "insert", e.v("c")),
        ),
    )


def module(e):
    x = []
    x.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    x.append(e.let("t_i32", e.fld(e.v("wasm"), "i32")))
    x.append(e.let("t_void", e.fld(e.v("wasm"), "void")))
    x.append(e.let("t_pv", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_void"))))
    x.append(e.let("t_pi32", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_i32"))))
    for name, params, ret in [
        ("malloc_t", ["t_i32"], "t_pv"),
        ("free_t", ["t_pv"], "t_void"),
        ("i32_t", ["t_i32"], "t_i32"),
        ("void_i32_t", ["t_i32"], "t_void"),
    ]:
        x.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "fn"),
                    e.rec(
                        p("params", e.list_new(e.mb.eval_type(), *[e.v(pn) for pn in params])),
                        p("ret", e.v(ret)),
                    ),
                ),
            )
        )
    x.append(
        e.let(
            "state",
            e.call(
                e.fld(e.v("wasm"), "alloc_dep"), e.rec(p("name", e.s("alloc_state")), p("size", e.int_of(STATE_SIZE)))
            ),
        )
    )
    # Helpers first: the bodies of later dependencies call them (lowered constants).
    for name, dep_name, params, fn_t, fbody in [
        ("binidx", "alloc_binidx", ("s",), "i32_t", _binidx_body(e)),
        ("insert", "alloc_insert", ("c",), "void_i32_t", _insert_body(e)),
        ("unlink", "alloc_unlink", ("c",), "void_i32_t", _unlink_body(e)),
        ("malloc", "malloc", ("n",), "malloc_t", _malloc_body(e)),
        ("free", "free", ("p",), "free_t", _free_body(e)),
    ]:
        x.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "func_dep"),
                    e.rec(
                        p("name", e.s(dep_name)),
                        p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
                        p("ty", e.v(fn_t)),
                        p("body", e.stage(fbody)),
                    ),
                ),
            )
        )
    x.append(e.ret(e.rec(p("malloc", e.v("malloc")), p("free", e.v("free")))))

    top = []
    top.append(e.ret(e.lower(e.mb.seq(x))))
    return top
