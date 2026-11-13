// Prefix with scrimFactorySource (the actual module source) and expectBroken.
// Run only through the guarded disposable-sleep runner, never in SystemUI.
if (!/\/(?:toybox|sleep)$/.test(Process.enumerateModules()[0].path)) {
    throw new Error('Lifetime probe requires a disposable /system/bin/sleep process');
}
const actualCModule = CModule;
let collected = 0;
function collectedModule() { collected++; }
function observedCModule(source, symbols) {
    const value = new actualCModule(source, symbols);
    Script.bindWeak(value, collectedModule);
    return value;
}
const offsets = [0x4e28710, 0x4e18e10, 0x4dbadac, 0x4e2c990, 0x4e96a54], low = Math.min(...offsets);
const codeSize = Math.ceil((Math.max(...offsets) - low + 128) / Process.pageSize) * Process.pageSize;
const code = Memory.alloc(codeSize);
Memory.protect(code, codeSize, 'rwx');
for (const offset of offsets.slice(0, 3)) {
    const entry = code.add(offset - low);
    [0xd503245f, offset === offsets[2] ? 0x9100e000 : 0xbd004400,
        0xd65f03c0, 0xd503245f, 0xbd004c00, 0xd65f03c0]
        .forEach((word, i) => entry.add(i * 4).writeU32(word));
}
// Keep the verified prologue and restore its saved registers before returning.
[0xd503233f, 0xd10603ff, 0xfd0093ec, 0x6d132beb, 0xbd007c00,
    0x6d532beb, 0xfd4093ec, 0x910603ff, 0xd50323bf, 0xd65f03c0]
    .forEach((word, i) => code.add(offsets[3] - low + i * 4).writeU32(word));
[0xd503233f, 0xd10583ff, 0xa9127bfd, 0xa9135ffc, 0xb9089c01,
    0xa9535ffc, 0xa9527bfd, 0x910583ff, 0xd50323bf, 0xd65f03c0]
    .forEach((word, i) => code.add(offsets[4] - low + i * 4).writeU32(word));
const backend = {base: code.sub(low), getExportByName(symbol) {
    return code.add(offsets[symbol.includes('HandRenderer') ? 4 : symbol.includes('SystemInputInfoStore') ? 2 : symbol.includes('5Scrim') ? 3 : symbol.includes('MultiSurface') ? 1 : 0] - low);
}};
const processDouble = {arch: Process.arch, pointerSize: Process.pointerSize,
    getModuleByName(name) {
        if (name !== 'libspaceflinger_jni_vulkan.so') throw new Error('Unexpected module');
        return backend;
    }};
// Only module lookup is doubled; native compilation, allocation, hooks and GC are real.
const factory = new Function('Process', 'CModule',
    scrimFactorySource.replaceAll('export ', '') + '\nreturn installPinnedScrim;')
    (processDouble, observedCModule);
const clock = new NativeFunction(Module.getGlobalExportByName('clock_gettime'), 'int', ['int', 'pointer']);
const stamp = Memory.alloc(16);
function now() {
    if (clock(1, stamp) !== 0) throw new Error('Clock failed');
    return stamp.readS64().toNumber() * 1000 + stamp.add(8).readS64().toNumber() / 1e6;
}
const receiver = Memory.alloc(0x90);
const setters = offsets.slice(0, 2).map(offset => new NativeFunction(code.add(offset - low), 'void', ['pointer', 'float']));
const setFullscreenAlpha = new NativeFunction(code.add(offsets[3] - low), 'void', ['pointer', 'float']);
const hand = Memory.alloc(0x900);
const setHandMode = new NativeFunction(code.add(offsets[4] - low), 'void', ['pointer', 'int']);
function checkHand(expected) {
    hand.add(0x898).writeU32(0x12345678); hand.add(0x8a0).writeU32(0x87654321);
    setHandMode(hand, 5);
    if (hand.add(0x89c).readU32() !== expected || hand.add(0x898).readU32() !== 0x12345678 ||
            hand.add(0x8a0).readU32() !== 0x87654321) throw new Error('Wrong hand draw mode or adjacent state');
}
const store = Memory.alloc(0x90), originalInfo = store.add(0x38);
originalInfo.writeByteArray(new Uint8Array(0x54).fill(0x5a));
originalInfo.add(0x38).writeU8(1);
const getter = new NativeFunction(code.add(offsets[2] - low), 'pointer', ['pointer']);
let escapedCopy = null;
function checkInput(expected) {
    const result = getter(store);
    if (result.equals(originalInfo) === expected) throw new Error('Wrong local pointer routing');
    if (originalInfo.add(0x38).readU8() !== 1) throw new Error('Shared input state was mutated');
    if (expected) {
        const bytes = new Uint8Array(result.readByteArray(0x54));
        if (bytes.some((value, i) => value !== (i === 0x38 ? 0 : 0x5a))) throw new Error('Wrong local input copy');
        escapedCopy = result;
    }
}
function checkAlpha(expected) {
    for (const setter of setters) {
        setter(receiver, .3);
        if (Math.abs(receiver.add(0x44).readFloat() - expected) > .0001) throw new Error('Wrong alpha');
    }
    receiver.add(0x78).writeU32(0x12345678); receiver.add(0x80).writeU32(0x87654321);
    setFullscreenAlpha(receiver, .2);
    const fullscreenExpected = expected === 1 ? 0 : .2;
    if (Math.abs(receiver.add(0x7c).readFloat() - fullscreenExpected) > .0001) throw new Error('Wrong fullscreen alpha');
    if (receiver.add(0x78).readU32() !== 0x12345678 || receiver.add(0x80).readU32() !== 0x87654321) {
        throw new Error('Fullscreen alpha changed adjacent state');
    }
}
let hook = factory(now), cycles = 0;
function fail(error) {
    Interceptor.detachAll(); Interceptor.flush();
    console.log('LIFETIME_PROBE_FAIL ' + error.stack);
}
function step() {
    gc();
    setTimeout(() => {
        try {
            if (expectBroken) {
                console.log('LIFETIME_COLLECTED ' + collected);
                let failed = false;
                try { hook.setAllowed(true); }
                catch (error) { failed = true; console.log('LIFETIME_ARM_FAILED ' + error); }
                // Do not call a clone while its native listener points into freed code.
                Interceptor.detachAll(); Interceptor.flush();
                if (!failed || collected === 0) throw new Error('Old bug was not reproduced');
                console.log('LIFETIME_BUG_REPRODUCED');
                return;
            }
            if (collected !== 0) throw new Error('Live controller lost its code owner');
            hook.setAllowed(true); hook.setHandsHidden(true); checkAlpha(1);
            hook.setInputAllowed(true); checkInput(true); checkHand(5);
            hook.setInputAllowed(false); checkInput(false); checkHand(0);
            const diagnostics = hook.getScrimDiagnostics();
            if (diagnostics.frames < 1 || diagnostics.suppressed < 1 || diagnostics.hiddenHands < 1 || Math.abs(diagnostics.meanAlpha - .2) > .001) {
                throw new Error('Missing fullscreen scrim diagnostics');
            }
            hook.setAllowed(false); hook.setHandsHidden(false); checkAlpha(.3); checkHand(5);
            checkInput(false);
            if (++cycles < 20) { step(); return; }
            hook.setAllowed(true);
            hook.setHandsHidden(true);
            hook.setInputAllowed(true);
            setTimeout(() => {
                try {
                    gc(); checkAlpha(.3); checkInput(false); checkHand(5);
                    hook.stop(); Interceptor.flush(); checkAlpha(.3); checkInput(false); checkHand(5);
                    hook = null;
                    gc();
                    setTimeout(() => {
                        if (collected !== 1) { fail(new Error('Stopped controller retained code')); return; }
                        if (escapedCopy.add(0x38).readU8() !== 0) { fail(new Error('Escaping input copy was freed')); return; }
                        console.log('LIFETIME_FIXED_PASSED cycles=' + cycles + ' released=' + collected);
                    }, 100);
                } catch (error) { fail(error); }
            }, 1100);
        } catch (error) { fail(error); }
    }, 20);
}
console.log('LIFETIME_INSTALLED');
step();
