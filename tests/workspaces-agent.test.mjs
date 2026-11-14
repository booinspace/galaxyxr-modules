import {test} from 'node:test';
import assert from 'node:assert/strict';
import {WorkspaceUpload, installWorkspaces, hasWorkspaceDexHeader} from '../scripts/curvature-workspaces-agent.mjs';

const token = 'a'.repeat(32), hash = 'b'.repeat(64);
test('workspace transfer requires exact token, size, ordering and deadline', () => {
    const upload = new WorkspaceUpload();
    assert.equal(upload.accept(`ws-begin ${token} ${hash} 4`, 10), null);
    upload.accept(`ws-part ${token} ZGV4Cg==`, 11);
    assert.deepEqual(upload.accept(`ws-end ${token}`, 12), {token, sha: hash, size: 4, data: 'ZGV4Cg==', started: 10});
    assert.throws(() => upload.accept(`ws-end ${token}`, 13));
    upload.accept(`ws-begin ${token} ${hash} 4`, 10);
    assert.throws(() => upload.accept(`ws-part ${'c'.repeat(32)} ZGV4Cg==`, 11));
    upload.accept(`ws-begin ${token} ${hash} 4`, 10);
    assert.throws(() => upload.accept(`ws-part ${token} ZGV4Cg==`, 15011));
    upload.accept(`ws-begin ${token} ${hash} 4`, 10);
    assert.throws(() => upload.accept(`ws-end ${token}`, 11));
});
test('reject oversized, overflowing and malformed input without a loader', () => {
    for (const text of [`ws-begin ${token} ${hash} 524289`, `ws-part ${token} !!!`, 'ws-end', 'ws-begin ' + 'a'.repeat(3500)]) {
        assert.throws(() => new WorkspaceUpload().accept(text, 0));
    }
    const upload = new WorkspaceUpload(); upload.accept(`ws-begin ${token} ${hash} 1`, 0);
    assert.throws(() => upload.accept(`ws-part ${token} ZGV4Cg==`, 1));
});
test('an inactive optional module leaves the parent runtime alone', () => {
    let errors = 0;
    const Java = {perform(fn) { fn(); }, use() { throw new Error('No Java operation expected while inactive'); }};
    const adapter = installWorkspaces(Java, {}, {}, {}, () => assert.fail('No curvature request expected'), () => true, () => 0, () => errors++);
    adapter.pulse(new Map());
    assert.equal(adapter.accept('pulse'), false);
    assert.equal(adapter.accept(`ws-ping ${token}`), true);
    assert.equal(adapter.status().running, false);
    assert.equal(adapter.isStopped(), true);
    adapter.accept('ws-invalid');
    assert.equal(errors, 1);
    adapter.stop(); adapter.pulse(new Map()); assert.equal(adapter.isStopped(), true);
});
test('bad payload failure is isolated from the main Window Controls runtime', () => {
    const logs = [];
    const Java = {perform(fn) { fn(); }, use(name) {
        if (name === 'android.util.Base64') return {decode() {return [100,101,120,10];}};
        if (name === 'java.security.MessageDigest') return {getInstance() {return {digest() {return new Array(32).fill(0);}};}};
        assert.fail('A bad digest must never reach the class loader');
    }};
    const adapter = installWorkspaces(Java, {}, {}, {}, () => false, () => true, () => 0, (kind) => logs.push(kind));
    adapter.accept(`ws-begin ${token} ${hash} 4`); adapter.accept(`ws-part ${token} ZGV4Cg==`); adapter.accept(`ws-end ${token}`);
    assert.equal(adapter.status().running, false); assert.ok(adapter.status().error.includes('checksum'));
    assert.deepEqual(logs, ['WORKSPACES_LOAD', 'WORKSPACES_ERROR']); assert.equal(adapter.isStopped(), true);
});

test('a 99 KB Java DEX checks only its four-byte header across the bridge', () => {
    const reads = [];
    const javaArray = new Proxy({length: 98951, 0: 100, 1: 101, 2: 120, 3: 10}, {
        get(target, key) {
            if (key === Symbol.iterator) throw new Error('Do not iterate over a Java byte array');
            if (/^[0-9]+$/.test(String(key))) {
                reads.push(Number(key));
                if (Number(key) >= 4) throw new Error('Read past the DEX header');
            }
            return Reflect.get(target, key);
        },
    });
    assert.equal(hasWorkspaceDexHeader(javaArray), true);
    assert.deepEqual(reads, [0, 1, 2, 3]);
    assert.equal(hasWorkspaceDexHeader([100, 101, 120]), false);
    assert.equal(hasWorkspaceDexHeader([100, 101, 121, 10]), false);
});

test('loading a real-sized helper never reads its body through indexed JavaScript access', () => {
    const count = 98951, reads = [], logs = [], hooks = [{implementation: null, call() {return 'native';}}, {implementation: null, call() {return 'native';}}];
    const bytes = new Proxy({length: count, 0: 100, 1: 101, 2: 120, 3: 10}, {get(target, key) {
        if (key === Symbol.iterator) throw new Error('Full Java array iteration blocks pulse delivery');
        if (/^[0-9]+$/.test(String(key))) { assert.ok(Number(key) < 4); reads.push(Number(key)); }
        return Reflect.get(target, key);
    }});
    let stopped = false, closed = false, attached = 0;
    const controller = {pulse() {}, stop() {stopped = true;}, isStopped: () => stopped,
        status: () => 'RUNNING', attachOverview() {attached++;}, $dispose() {}};
    const bridge = {pulse() {}, close() {closed = true;}, updateCurvatures() {}, poll: () => '', $dispose() {}};
    const child = {use(name) {assert.equal(name, 'local.gxr.workspaces.WorkspaceController'); return {$new: () => controller};}};
    const factory = {loader: {}, use(name) {assert.equal(name, 'local.gxr.workspacehost.WorkspaceWindowHost'); return {$new: () => bridge};}};
    const classes = {
        'android.util.Base64': {decode: () => bytes},
        'java.security.MessageDigest': {getInstance: () => ({digest: () => new Array(32).fill(-69)})},
        'java.nio.ByteBuffer': {wrap: value => value},
        'dalvik.system.InMemoryDexClassLoader': {$new: () => ({})},
        'android.app.ActivityThread': {currentApplication: () => ({getApplicationContext: () => ({})})},
        'com.android.systemui.xr.overview.ui.OverviewXrElement': {onCreate: {overload: () => hooks[0]}, onResume: {overload: () => hooks[1]}},
    };
    const Java = {use(name) {assert.ok(classes[name], name);return classes[name];}, perform: fn => fn(), retain: value => value,
        ClassFactory: {get: () => child}, array: (_type, values) => values};
    const adapter = installWorkspaces(Java, factory, {}, {}, () => false, () => true, () => 10, kind => logs.push(kind));
    adapter.accept(`ws-begin ${token} ${hash} ${count}`);
    const payload = 'A'.repeat(Math.ceil(count / 3) * 4);
    for (let start = 0; start < payload.length; start += 2800) adapter.accept(`ws-part ${token} ${payload.slice(start, start + 2800)}`);
    adapter.accept(`ws-end ${token}`);
    assert.equal(adapter.status().running, true); assert.deepEqual(reads, [0, 1, 2, 3]);
    assert.ok(logs.includes('WORKSPACES_READY')); assert.ok(!logs.includes('WORKSPACES_ERROR'));
    assert.equal(hooks[1].implementation.call({}), 'native'); assert.equal(attached, 1);
    adapter.pulse(new Map()); adapter.stop(); assert.equal(adapter.isStopped(), true);
    assert.equal(closed, true); assert.ok(hooks.every(hook => hook.implementation === null));
});
