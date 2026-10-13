"""The ecosystem's projects: each a directory under `builders/` (a Python package) and under `code/` (its modules).
Every entry is (module file, builder module, extra builder args); `project_of` finds a file's project, so a module
importing another names only the file."""

from .root_mode import APP, IR

PROJECTS = {
    "wasm": [
        ("wasm-alloc.atz", "wasm_alloc", ()),
        ("wasm-alloc-test.atz", "wasm_alloc_test", ()),
        ("wat-2.0.atz", "wat", ()),
    ],
    "wasi": [
        ("wasi-0.1.atz", "wasi", ()),
        ("hello-wasi.atz", "hello_wasi", ("app",)),
        ("hello-wasi-wat.atz", "hello_wasi", ("wat",)),
    ],
    "llvm": [
        ("llvm-ir-22.atz", "llvm_ir", ()),
    ],
    "libc": [
        ("libc-2.42.atz", "libc", ()),
    ],
    "javascript": [
        ("js-es2020.atz", "js", ()),
    ],
    "glsl": [
        ("glsl-es-3.00.atz", "glsl", ()),
    ],
    "web": [
        ("webidl.atz", "webidl", ()),
        ("webidl-wasm.atz", "webidl_wasm", ()),
        ("webidl-js.atz", "webidl_js", ()),
        ("web-wasm.atz", "web_wasm", ()),
        ("hello-web.atz", "hello_web", ()),
        ("webgl-uniforms.atz", "webgl_uniforms", ()),
        ("web-wiggle.atz", "web_wiggle", ()),
    ],
    "pipewire": [
        ("spa-pod-1.6.atz", "spa_pod", ()),
        ("pipewire-1.6.atz", "pipewire", ()),
    ],
    "synth": [
        ("synth-midi-sine.atz", "synth", (APP,)),
        ("synth-midi-sine-ir.atz", "synth", (IR,)),
    ],
    "buzz": [
        ("buzz-dsp.atz", "buzz_dsp", ()),
        ("buzz-samplegrid.atz", "buzz_sample_grid", ()),
        ("buzz-unwieldytracker.atz", "buzz_unwieldy_tracker", ()),
        ("buzz-m4.atz", "buzz_m4", ()),
        ("buzz-infector.atz", "buzz_infector", ()),
        ("buzz-tunaman.atz", "buzz_tuna_man", ()),
        ("buzz-ninja.atz", "buzz_ninja", ()),
        ("buzz-m4wii.atz", "buzz_m4wii", ()),
        ("buzz-classiceq.atz", "buzz_classic_eq", ()),
        ("buzz-karmafilter.atz", "buzz_karma_filter", ()),
        ("buzz-kaway.atz", "buzz_kaway", ()),
        ("buzz-bloodoverdrive.atz", "buzz_blood_overdrive", ()),
        ("buzz-bluecatphaser.atz", "buzz_blue_cat_phaser", ()),
        ("buzz-gunpowder-valentine.atz", "buzz_gunpowder", (APP,)),
        ("buzz-gunpowder-valentine-ir.atz", "buzz_gunpowder", (IR,)),
    ],
    "merman": [
        ("merman-editor.atz", "merman_editor", ()),
        ("stylus-recorder.atz", "stylus_recorder", ()),
    ],
    "core": [
        ("meta.atz", "meta", ()),
        ("values.atz", "values", ()),
        ("values-test.atz", "values_test", ("llvm",)),
        ("values-test-wasm.atz", "values_test", ("wasm",)),
    ],
    "memory": [
        ("destructor.atz", "destructor", ()),
        ("destructor-test.atz", "destructor_test", ("app",)),
        ("destructor-test-err.atz", "destructor_test", ("err",)),
        ("lifetimes.atz", "lifetimes", ()),
        ("lifetimes-test.atz", "lifetimes_test", ("app",)),
        ("lifetimes-test-err.atz", "lifetimes_test", ("err",)),
        ("readonly.atz", "readonly", ()),
        ("readonly-test.atz", "readonly_test", ("app",)),
        ("readonly-test-err-ro.atz", "readonly_test", ("err_ro",)),
        ("readonly-test-err-sealed.atz", "readonly_test", ("err_sealed",)),
        ("destructor-test-wasm.atz", "destructor_test_wasm", ()),
        ("shared-wasm.atz", "shared", ("wasm",)),
        ("shared-llvm.atz", "shared", ("llvm",)),
        ("shared-test-wasm.atz", "shared_test_wasm", ()),
        ("shared-test.atz", "shared_test", ()),
    ],
    "json": [
        ("json.atz", "json", ()),
        ("json-wasm.atz", "json_target", ("wasm",)),
        ("json-llvm.atz", "json_target", ("llvm",)),
        ("json-echo-wasi.atz", "json_echo", ("wasm",)),
        ("json-echo-libc.atz", "json_echo", ("llvm",)),
        ("json-echo-libc-ir.atz", "json_echo", ("llvm", "ir")),
    ],
    "collections": [
        ("slice-wasm.atz", "slice", ("wasm",)),
        ("slice-llvm.atz", "slice", ("llvm",)),
        ("option-wasm.atz", "option", ("wasm",)),
        ("option-llvm.atz", "option", ("llvm",)),
        ("vec-wasm.atz", "vec", ("wasm",)),
        ("vec-llvm.atz", "vec", ("llvm",)),
        ("vec-test-wasm.atz", "vec_test_wasm", ()),
        ("vec-test.atz", "vec_test", ()),
        ("vec-trap-wasm.atz", "vec_trap_test", ("wasm",)),
        ("vec-trap.atz", "vec_trap_test", ("llvm",)),
        ("tuple-test-wasm.atz", "tuple_test", ("wasm",)),
        ("tuple-test.atz", "tuple_test", ("llvm",)),
        ("option-test-wasm.atz", "option_test", ("wasm",)),
        ("option-test.atz", "option_test", ("llvm",)),
        ("map-wasm.atz", "hashmap", ("wasm", True)),
        ("map-llvm.atz", "hashmap", ("llvm", True)),
        ("set-wasm.atz", "hashmap", ("wasm", False)),
        ("set-llvm.atz", "hashmap", ("llvm", False)),
        ("hashmap-test-wasm.atz", "hashmap_test_wasm", ()),
        ("hashmap-test.atz", "hashmap_test", ()),
    ],
}


def modules():
    """All (project, file, builder module, args) entries."""
    return [(p, f, s, a) for p, items in PROJECTS.items() for f, s, a in items]


def project_of(file):
    """The project of the registered module file `file`."""
    for p, items in PROJECTS.items():
        for f, _, _ in items:
            if f == file:
                return p
    raise KeyError(file)
