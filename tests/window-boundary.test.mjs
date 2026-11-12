import test from 'node:test';
import assert from 'node:assert/strict';
import {boundaryTransform, installBoundaryAlignment} from '../scripts/curvature-boundary-agent.mjs';

const identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
const turn = [0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, .2, .3, .4, 1];
const baseline = [2, 0, 0, 0, 0, 3, 0, 0, 0, 0, 1, 0, .1, .2, .01, 1];
function near(actual, expected) { actual.forEach((v, i) => assert.ok(Math.abs(v - expected[i]) < 1e-5, `${i}: ${v} != ${expected[i]}`)); }

test('boundary corners follow the content rotation, scale and offset', () => {
    const aligned = boundaryTransform(turn, baseline);
    near(aligned, [0, 2, 0, 0, -3, 0, 0, 0, 0, 0, 1, 0, 0, .4, .41, 1]);
    const pitch = [1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1];
    const yaw = [0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1];
    near(boundaryTransform(pitch, baseline), [2, 0, 0, 0, 0, 0, 3, 0, 0, -1, 0, 0, .1, -.01, .2, 1]);
    near(boundaryTransform(yaw, baseline), [0, 0, -2, 0, 0, 3, 0, 0, 1, 0, 0, 0, .01, .2, -.1, 1]);
    for (const bad of [[], identity.map(() => NaN), identity.map(() => Infinity), identity.map(() => 1e8)]) {
        assert.throws(() => boundaryTransform(bad, baseline), /Invalid/);
    }
    const perspective = identity.slice(); perspective[3] = .1;
    assert.throws(() => boundaryTransform(perspective, baseline), /Invalid/);
});

function fixture({wrongPin = false, oversizedChildren = false} = {}) {
    const memory = Buffer.alloc(1 << 20), scene = new Map(), callbacks = new Map(), errors = [], frees = [];
    let next = 1024, writes = 0;
    class Pointer {
        constructor(address) { this.address = Number(address); }
        add(n) { return new Pointer(this.address + n); }
        sub(other) { return new Pointer(this.address - other.address); }
        equals(other) { return this.address === other.address; }
        toString() { return String(this.address); }
        toInt32() { return this.address | 0; }
        isNull() { return this.address === 0; }
        readU64() { return memory.readBigUInt64LE(this.address); }
        readU32() { return memory.readUInt32LE(this.address); }
        writeU64(v) { memory.writeBigUInt64LE(BigInt(v.toString()), this.address); }
        readPointer() { return new Pointer(this.readU64()); }
        writePointer(p) { this.writeU64(p.address); }
        readFloat() { return memory.readFloatLE(this.address); }
        writeFloat(v) { memory.writeFloatLE(v, this.address); }
        readUtf8String(n) { return memory.toString('utf8', this.address, this.address + n); }
    }
    const ptr = n => new Pointer(n);
    const alloc = size => { const p = ptr(next); next += size + 16; return p; };
    const parts = id => [BigInt(id), ptr(id * 16)];
    function nodeHandle(id) { const p = alloc(16); p.writeU64(id); p.add(8).writePointer(ptr(id * 16)); return p; }
    function node(id, name, parent, matrix = identity) {
        const data = alloc(64), text = alloc(name.length + 1);
        matrix.forEach((v, i) => data.add(i * 4).writeFloat(v));
        memory.write(name, text.address);
        scene.set(id, {id, name, parent, data, text, valid: true});
    }
    node(1, 'space-transform-task-42', 0);
    node(2, 'window-task-42', 1, turn);
    node(3, 'Highlight', 1, baseline);
    node(4, 'Resize Placeholder Visual', 1, baseline);
    const at = p => scene.get(p.readU32());
    const symbols = new Map();
    const implementations = {
        '_ZNK3imp9Component7GetNodeEv': p => parts(p.address === 301 ? 3 : 4),
        '_ZNK3imp10NodeHandle7IsValidEv': p => Boolean(at(p)?.valid),
        '_ZNK3imp4Node9GetParentEv': p => [BigInt(at(p).parent) | (0xfff0n << 32n), ptr(at(p).parent * 16)],
        '_ZNK3imp4Node7GetNameEv': p => [at(p).text, at(p).name.length],
        '_ZNK3imp4Node11GetChildrenEv': p => {
            const nodes = [...scene.values()].filter(n => n.parent === at(p).id);
            const data = alloc(nodes.length * 16);
            nodes.forEach((n, i) => {
                data.add(i * 16).writeU64(n.id);
                data.add(i * 16 + 8).writePointer(ptr(n.id * 16));
            });
            return [data, data.add((oversizedChildren ? 65 : nodes.length) * 16), data.add(nodes.length * 16)];
        },
        '_ZNK3imp4Node11GetLocalTrsEv': p => at(p).data,
        '_ZN3imp4Node11SetLocalTrsERKN8filament4math7details6TMat44IfEE': (p, data) => {
            assert.ok(at(p).valid, 'must not write a released node');
            memory.copy(memory, at(p).data.address, data.address, data.address + 64); writes++;
        },
        '_ZdlPv': p => frees.push(p.address),
    };
    const offsets = [0x12e24f8, 0x12f1964, 0x12ec70c, 0x12ebe2c, 0x12ec75c, 0x12ecc64, 0x12ec510];
    Object.keys(implementations).slice(0, 7).forEach((s, i) => symbols.set(s, offsets[i]));
    for (const [type, values] of [['15HighlightVisual', [0x4d0ba98, 0x4d0c194, 0x4c97c60, 0x4c97d30]],
        ['23ResizePlaceholderVisual', [0x4d1622c, 0x4d16074, 0x4c99828, 0x4c998f8]]]) {
        const names = [`_ZN2ix6moohan5sysui${type}6UpdateERKN3imp9FrameTimeE`,
            `_ZN2ix6moohan5sysui${type}21UpdateSizeAndPositionERKN8filament4math7details5TVec2IfEERKNS5_5TVec3IfEE`,
            `_ZN3imp13ComponentPoolIN2ix6moohan5sysui${type}EE12NotifyActiveEPNS_9ComponentEb`,
            `_ZN3imp13ComponentPoolIN2ix6moohan5sysui${type}EE7CleanupERNS_9ComponentE`];
        names.forEach((s, i) => symbols.set(s, values[i]));
    }
    globalThis.Memory = {alloc, copy: (a, b, size) => memory.copy(memory, a.address, b.address, b.address + size)};
    const exported = (s, base) => { const p = ptr(base + symbols.get(s) + (wrongPin ? 4 : 0)); p.symbol = s; return p; };
    globalThis.Process = {getModuleByName: n => {
        assert.ok(['libImpress-jni-vulkan.so', 'libsysui_jni_soong_vulkan.so'].includes(n), 'wrong renderer target: ' + n);
        const base = n.startsWith('libImpress') ? 0x20000000 : 0x10000000;
        return {name: n, base: ptr(base), getExportByName: s => exported(s, base)};
    }};
    globalThis.Module = {getGlobalExportByName: s => { const p = ptr(1); p.symbol = s; return p; }};
    globalThis.NativeFunction = function (p) { assert.ok(implementations[p.symbol]); return implementations[p.symbol]; };
    globalThis.Interceptor = {attach: (p, callback) => {
        callbacks.set(p.symbol, callback);
        return {detach: () => callbacks.delete(p.symbol)};
    }};
    const allowed = new Set([42]);
    function invoke(fragment, component = 301, original = () => {}) {
        const symbol = [...callbacks.keys()].find(s => s.includes(fragment));
        assert.ok(symbol, fragment);
        const callback = callbacks.get(symbol), context = {};
        callback.onEnter?.call(context, [ptr(component), ptr(component), ptr(0)]);
        original();
        callback.onLeave?.call(context);
    }
    const read = id => Array.from({length: 16}, (_, i) => scene.get(id).data.add(i * 4).readFloat());
    return {scene, allowed, errors, frees, callbacks, invoke, read, node, nodeHandle, ptr,
        start: () => installBoundaryAlignment(id => allowed.has(id), e => errors.push(e)), get writes() { return writes; }};
}

test('native visuals align once per frame, preserve stock resize, and wait for cleanup', () => {
    const f = fixture(), boundary = f.start();
    const update = '15HighlightVisual6Update', resize = '15HighlightVisual21UpdateSizeAndPosition';
    f.invoke(update, 301, () => f.invoke(resize));
    near(f.read(3), boundaryTransform(turn, baseline));
    let diagnostics = boundary.getDiagnostics();
    assert.equal(diagnostics.renderer, 'libsysui_jni_soong_vulkan.so');
    assert.equal(diagnostics.highlightUpdates, 1);
    assert.equal(diagnostics.resizes, 1);
    assert.equal(diagnostics.aligned, 1);
    assert.equal(diagnostics.last, 'aligned');
    assert.ok(diagnostics.path.includes('window-task-42'));
    diagnostics.parents.length = 0;
    assert.deepEqual(boundary.getDiagnostics().parents, ['space-transform-task-42']);
    f.invoke(update, 301, () => near(f.read(3), baseline));
    near(f.read(3), boundaryTransform(turn, baseline)); // No cumulative rotation.
    f.invoke('23ResizePlaceholderVisual6Update', 302);
    assert.equal(boundary.getDiagnostics().placeholderUpdates, 1);
    near(f.read(4), boundaryTransform(turn, baseline));
    const newSize = baseline.slice(); newSize[0] = 4;
    f.invoke(resize, 301, () => newSize.forEach((v, i) => f.scene.get(3).data.add(i * 4).writeFloat(v)));
    near(f.read(3), boundaryTransform(turn, newSize));
    assert.ok(f.frees.length > 0, 'returned child vectors must be freed');
    boundary.stop();
    assert.equal(boundary.isRestored(), false);
    assert.throws(() => boundary.dispose(), /pending/);
    f.invoke(update); near(f.read(3), newSize);
    assert.equal(boundary.isRestored(), false);
    f.invoke('23ResizePlaceholderVisualEE12NotifyActive', 302);
    near(f.read(4), baseline);
    assert.equal(boundary.isRestored(), true);
    boundary.dispose(); assert.equal(f.callbacks.size, 0); assert.deepEqual(f.errors, []);
});

test('node loss, eligibility loss and hierarchy changes leave no stale writes', () => {
    const f = fixture(), boundary = f.start();
    f.invoke('15HighlightVisual6Update');
    f.allowed.clear(); f.invoke('15HighlightVisual6Update'); near(f.read(3), baseline);
    f.allowed.add(42); f.invoke('15HighlightVisual6Update');
    f.scene.get(3).valid = false;
    const before = f.writes;
    f.invoke('15HighlightVisualEE7Cleanup'); assert.equal(f.writes, before);
    f.node(3, 'Highlight', 1, baseline);
    const leash = identity.slice(); leash[12] = .3;
    f.node(5, 'window-leash', 1, leash);
    f.scene.get(2).parent = 5;
    f.invoke('15HighlightVisual6Update'); // A bounded intermediate transform is supported.
    near(f.read(3), boundaryTransform(boundaryTransform(leash, turn), baseline));
    boundary.stop(); f.invoke('15HighlightVisual6Update');
    assert.equal(boundary.isRestored(), true); boundary.dispose();
    assert.deepEqual(f.errors, []);
});

test('ABI pin mismatch installs no hooks', () => {
    const f = fixture({wrongPin: true});
    assert.throws(() => f.start(), /symbol mismatch/);
    assert.equal(f.callbacks.size, 0);
});

test('unrepresentable transitions are skipped and malformed child vectors are freed', () => {
    const f = fixture(), boundary = f.start();
    const nonuniform = turn.slice(); nonuniform[1] = 2;
    nonuniform.forEach((v, i) => f.scene.get(2).data.add(i * 4).writeFloat(v));
    f.invoke('15HighlightVisual6Update'); near(f.read(3), baseline);
    assert.equal(f.writes, 0);
    assert.equal(boundary.getDiagnostics().last, 'nonuniform-or-skewed');
    boundary.stop(); assert.equal(boundary.isRestored(), true); boundary.dispose();
    const bad = fixture({oversizedChildren: true}), failed = bad.start();
    bad.invoke('15HighlightVisual6Update');
    assert.equal(bad.errors.length, 1);
    assert.match(String(bad.errors[0]), /child count/);
    assert.equal(bad.frees.length, 1);
    assert.equal(bad.writes, 0);
    assert.equal(failed.isRestored(), true); failed.dispose();
});

test('diagnostics distinguish absent callbacks, unmatched parents, missing windows and eligibility', () => {
    const f = fixture(), boundary = f.start();
    assert.equal(boundary.getDiagnostics().last, 'waiting-for-callback');
    f.node(1, 'unmatched-parent', 0);
    f.invoke('15HighlightVisual6Update');
    assert.equal(boundary.getDiagnostics().rejected['parent-name'], 1);
    assert.ok(boundary.getDiagnostics().parents.includes('unmatched-parent'));
    f.node(1, 'space-transform-task-42', 0);
    f.allowed.clear(); f.invoke('15HighlightVisual6Update');
    assert.equal(boundary.getDiagnostics().last, 'task-not-ready');
    f.allowed.add(42);
    f.node(2, 'other-window', 1);
    f.invoke('15HighlightVisual6Update');
    assert.equal(boundary.getDiagnostics().last, 'window-missing');
    assert.ok(boundary.getDiagnostics().path.includes('other-window'));
    f.node(2, 'window-task-42', 1);
    f.invoke('15HighlightVisual6Update');
    assert.equal(boundary.getDiagnostics().last, 'identity');
    assert.equal(f.writes, 0);
    boundary.stop(); boundary.dispose();
});
