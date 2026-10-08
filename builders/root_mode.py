"""How an llvm app module ends: build an executable (APP) or log the rendered IR (IR)."""

APP = "app"
IR = "ir"


def root_mode_finish(mode, e, llvm, ll):
    if mode == APP:
        return e.ret(e.call(e.fld(llvm, "build"), e.call_m0(ll, "render")))
    if mode == IR:
        return e.call(e.mb.log(), e.fld(e.call_m0(ll, "render"), "ir"))
    raise AssertionError(mode)
