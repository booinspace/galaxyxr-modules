import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

const source = readFileSync(process.argv[2], 'utf8');
const start = source.indexOf('class ArtQuickCodeInterceptor {');
const end = source.indexOf('\nfunction isArtQuickEntrypoint', start);
assert.ok(start >= 0 && end > start, 'Pinned bridge interceptor was not found');

function fixture(failure = '') {
    const trace = [];
    let suspended = false;
    const context = {
        Process: {arch: 'arm64'},
        withAllArtThreadsSuspended(callback) {
            assert.equal(suspended, false);
            suspended = true; trace.push('suspend');
            try { callback(); } finally { suspended = false; trace.push('resume'); }
        },
        artQuickCodeReplacementTrampolineWriters: {arm64: () => 16},
        artQuickCodePrologueWriters: {arm64() {
            assert.equal(suspended, true); trace.push('install');
            if (failure === 'install') throw new Error('install failed');
        }},
        Memory: {
            dup: () => ({readByteArray: length => Buffer.alloc(length)}),
            patchCode(address, length, callback) {
                assert.equal(suspended, true); trace.push('restore');
                if (failure === 'restore') throw new Error('restore failed');
                callback(address);
            },
        },
        thunkWriters: {arm64: class {
            putBytes(bytes) { assert.equal(suspended, true); assert.equal(bytes.length, 16); }
            flush() { assert.equal(suspended, true); }
        }},
    };
    runInNewContext(source.slice(start, end) + '\nglobalThis.Target = ArtQuickCodeInterceptor;', context);
    const target = new context.Target({});
    target._allocateTrampoline = () => {
        target.redirectSize = 16; target.trampoline = {};
        return {};
    };
    target._destroyTrampoline = () => {
        assert.equal(suspended, true); trace.push('release');
    };
    return {target, trace};
}

test('install and restoration keep code writes and trampoline release inside ART suspension', () => {
    const f = fixture();
    f.target.activate({});
    f.target.deactivate();
    assert.deepEqual(f.trace, ['suspend', 'install', 'resume', 'suspend', 'restore', 'release', 'resume']);
});

test('a failed code write always resumes ART and retains the trampoline for cleanup', () => {
    const install = fixture('install');
    assert.throws(() => install.target.activate({}), /install failed/);
    assert.deepEqual(install.trace, ['suspend', 'install', 'resume']);
    const restore = fixture('restore');
    restore.target.activate({});
    assert.throws(() => restore.target.deactivate(), /restore failed/);
    assert.deepEqual(restore.trace.slice(-3), ['suspend', 'restore', 'resume']);
    assert.ok(!restore.trace.includes('release'));
});

const factorySource = readFileSync(process.argv[3], 'utf8');
const prototypeStart = factorySource.indexOf('methodPrototype = Object.create(');
assert.ok(prototypeStart >= 0, 'Pinned bridge method prototype was not found');
const property = factorySource.slice(prototypeStart).match(/  implementation: \{\n([\s\S]*?)\n  \},\n  returnType:/);
assert.ok(property, 'Pinned bridge implementation setter was not found');

function callbackFixture(failRevert = false) {
    const retired = [], patched = new Set(), calls = [];
    const context = {
        retiredImplementations: retired,
        CONSTRUCTOR_METHOD: 0, INSTANCE_METHOD: 1, vm: {}, api: {},
    };
    assert.match(factorySource, /const retiredImplementations = \[\];/);
    runInNewContext('globalThis.descriptor = ({' + property[1] + '\n});', context);
    const replacement = {_m: {revert() {
        calls.push('revert');
        if (failRevert) throw new Error('revert failed');
    }}};
    const method = {_p: ['sample', {$f: {_patchedMethods: patched}}, 1], _r: replacement};
    Object.defineProperty(method, 'implementation', context.descriptor);
    patched.add(method);
    return {method, replacement, retired, patched, calls};
}

test('unhooked JNI callbacks remain alive through script teardown for in-flight callers', () => {
    const f = callbackFixture();
    f.method.implementation = null;
    assert.equal(f.method._r, undefined);
    assert.equal(f.patched.size, 0);
    assert.deepEqual(f.calls, ['revert']);
    assert.equal(f.retired[0], f.replacement);
    f.method.implementation = null;
    assert.equal(f.retired.length, 1);
});

test('a failed unhook keeps the existing callback attached and reachable', () => {
    const f = callbackFixture(true);
    assert.throws(() => { f.method.implementation = null; }, /revert failed/);
    assert.equal(f.method._r, f.replacement);
    assert.equal(f.retired.length, 0);
});
