import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {parseFeatureCommand, applyFeatureSettings} from '../scripts/curvature-features-agent.mjs';

const source = readFileSync(process.argv[2], 'utf8').replace(/^import .*;\n/gm, '');
const withRotation = process.argv.includes('--rotation');
const withBoundary = process.argv.includes('--boundary');
const withHomePins = process.argv.includes('--home-pins');

function session({homePinsUnavailable = false} = {}) {
    const timers = new Map(), intervals = new Map(), logs = [];
    let attached = 0, pulses = 0, stopRequests = 0, restored = false, id = 0;
    let rotationRestored = false, rotationStops = 0, rotationError = '', home = true;
    let boundaryRestored = !withBoundary, boundaryStops = 0, boundaryDisposals = 0;
    let boundaryPermission = () => false;
    let distancePermission = () => false;
    let homePinsRestored = !withHomePins, homePinsStops = 0, homePinsDisposals = 0;
    let homePinsPermission = () => false;
    const rotationPulses = [];
    const rotation = {
        setEnabled() {}, setGrabEnabled() {},
        getBoundTaskIds: () => home ? [42] : [],
        pulse: value => rotationPulses.push(value),
        shutdown() { rotationStops++; },
        isRestored: () => rotationRestored,
        getError: () => rotationError,
        getStatus: () => 'sessions=0,pending=0',
    };
    const menuShow = {implementation: null};
    const factory = {use(name) {
        if (name === 'local.gxr.rotation.WindowFeatures') return {curvature: {value: true}};
        if (name === 'local.gxr.rotation.RotationController') return {$new: () => rotation};
        if (name === 'local.gxr.curvature.MenuAttachment') {
            return {setRotationController: controller => assert.equal(controller, rotation)};
        }
        return {};
    }};
    const observer = {getCurrentlyRenderingOpenXrTaskId: () => ({getValue: () => home ? null : 42})};
    const classes = {
        'android.util.Base64': {decode: () => []},
        'dalvik.system.InMemoryDexClassLoader': {$new: () => ({})},
        'java.nio.ByteBuffer': {wrap: value => value},
        'java.lang.ClassLoader': {getSystemClassLoader: () => ({})},
        'java.lang.System': {},
        'com.android.systemui.xr.spatial.impl.TaskSubspaceImpl': {},
        'com.android.wm.shell.windowdecor.XrCaptionMenu': {show: {overload: () => menuShow}},
    };
    const context = {
        parseFeatureCommand, applyFeatureSettings,
        installGrabRotation: () => ({setEnabled() {}, pulse() {}, stop() {}}),
        installHomePins: (_Java, allowed) => {
            if (homePinsUnavailable) throw new Error('Home API unavailable');
            homePinsPermission = allowed;
            return {stop() { homePinsStops++; }, isRestored: () => homePinsRestored,
                getDiagnostics: () => ({limit: 50}),
                dispose() { assert.ok(homePinsRestored); homePinsDisposals++; }};
        },
        installBoundaryAlignment: (allowed, _onError, distanceAllowed) => {
            boundaryPermission = allowed;
            distancePermission = distanceAllowed;
            return {stop() { boundaryStops++; }, getDiagnostics: () => ({aligned: 0}), isRestored: () => boundaryRestored,
                dispose() { assert.ok(boundaryRestored); boundaryDisposals++; }};
        },
        Java: {
            use(name) { assert.ok(classes[name], name); return classes[name]; },
            ClassFactory: {get: () => factory}, perform: cb => cb(), retain: value => value,
            choose(name, callbacks) {
                callbacks.onMatch(name.endsWith('MixedRealityStateObserver') ? observer : {});
                callbacks.onComplete();
            },
        },
        rpc: {}, DEX_BASE64: '', console: {log: value => logs.push(value)},
        Memory: {alloc: () => ({})},
        Process: {id: 42, getModuleByName: () => ({getExportByName: () => ({})})},
        NativeFunction: function () { return () => 0; },
        setTimeout(cb, delay) { const timer = ++id; timers.set(timer, {cb, delay}); return timer; },
        clearTimeout: timer => timers.delete(timer),
        setInterval(cb) { const timer = ++id; intervals.set(timer, cb); return timer; },
        clearInterval: timer => intervals.delete(timer),
        installBorderless() {
            attached++;
            return {setEnabled() {}, pulse() { pulses++; }, stop() { stopRequests++; }, isStopped: () => restored};
        },
    };
    runInNewContext(source + '\ninstallNative = () => {}; nowMs = () => 0; this.pollAgent = poll;', context);
    return {context, timers, intervals, logs, attached: () => attached, pulses: () => pulses,
        stopRequests: () => stopRequests, restored() { restored = true; }, rotationPulses,
        rotationStops: () => rotationStops, restoreRotation() { rotationRestored = true; },
        rotationFailure() { rotationError = 'orientation update failed'; },
        leaveHome() { home = false; },
        restoreBoundary() { boundaryRestored = true; },
        boundaryStops: () => boundaryStops, boundaryDisposals: () => boundaryDisposals,
        boundaryAllowed: id => boundaryPermission(id),
        distanceAllowed: id => distancePermission(id),
        restoreHomePins() { homePinsRestored = true; },
        homePinsStops: () => homePinsStops, homePinsDisposals: () => homePinsDisposals,
        homePinsAllowed: () => homePinsPermission(),
    };
}

const cancelled = session();
await cancelled.context.rpc.exports.init();
assert.equal(cancelled.attached(), 0);
assert.equal([...cancelled.timers.values()][0].delay, 45000);
const pending = [...cancelled.timers.values()][0].cb;
cancelled.context.rpc.exports.onFridaStdin('stop');
assert.equal(cancelled.timers.size, 0);
pending();
assert.equal(cancelled.attached(), 0, 'cancelled or stale delayed callback must not attach');
cancelled.restoreRotation();
cancelled.restoreBoundary();
cancelled.restoreHomePins();
cancelled.context.pollAgent();
assert.equal(cancelled.intervals.size, 0);

const running = session();
await running.context.rpc.exports.init();
[...running.timers.values()][0].cb();
assert.equal(running.attached(), 1);
running.context.pollAgent();
assert.equal(running.pulses(), 1);
if (withBoundary) {
    assert.equal(running.boundaryAllowed(42), true, 'rotation binding does not require a Curve menu');
    running.context.rpc.exports.onFridaStdin('features 1 1 0 0');
    assert.equal(running.boundaryAllowed(42), false);
    assert.equal(running.distanceAllowed(42), true, 'distance remains available with rotation off');
    running.context.rpc.exports.onFridaStdin('features 1 1 1 0');
}
if (withRotation) {
    assert.deepEqual(running.rotationPulses, [true]);
    running.leaveHome();
    running.context.pollAgent();
    assert.equal(running.rotationPulses.at(-1), false);
    if (withBoundary) assert.equal(running.boundaryAllowed(42), false, 'Home Space exit revokes boundary eligibility');
    if (withBoundary) assert.equal(running.distanceAllowed(42), false, 'Home Space exit revokes distance changes');
    if (withHomePins) assert.equal(running.homePinsAllowed(), true, 'Home pin hooks have their own supervisor lease');
}
running.context.rpc.exports.onFridaStdin('stop');
assert.equal(running.stopRequests(), 1);
running.context.pollAgent();
assert.equal(running.intervals.size, 1, 'must wait for caption restoration before detach');
running.restored();
if (withRotation) {
    running.context.pollAgent();
    assert.equal(running.intervals.size, 1, 'must also wait for orientation restoration');
    assert.equal(running.rotationStops(), 1);
}
running.restoreRotation();
if (withBoundary) {
    running.context.pollAgent();
    assert.equal(running.intervals.size, 1, 'must wait for native boundary restoration');
    assert.equal(running.boundaryStops(), 1);
    assert.equal(running.boundaryDisposals(), 0);
}
running.restoreBoundary();
if (withHomePins) {
    running.context.pollAgent();
    assert.equal(running.intervals.size, 1, 'must wait for Home layout restoration');
    assert.equal(running.homePinsStops(), 1);
    assert.equal(running.homePinsDisposals(), 0);
}
running.restoreHomePins();
running.context.pollAgent();
if (withBoundary) assert.equal(running.boundaryDisposals(), 1);
if (withHomePins) assert.equal(running.homePinsDisposals(), 1);
assert.equal(running.intervals.size, 0);
assert.ok(running.logs.some(line => line.startsWith('GXR_CURVATURE_STOPPED')));
console.log('PASS: 45-second delayed attach, cancelled startup, pulses, and restoration before detach');
if (withRotation) {
    const failed = session();
    await failed.context.rpc.exports.init();
    [...failed.timers.values()][0].cb();
    failed.rotationFailure();
    failed.context.pollAgent();
    assert.equal(failed.rotationStops(), 1);
    assert.equal(failed.stopRequests(), 1);
    assert.ok(failed.logs.some(line => line.startsWith('GXR_CURVATURE_FATAL')));
    failed.restored(); failed.restoreRotation(); failed.restoreBoundary(); failed.restoreHomePins(); failed.context.pollAgent();
    assert.equal(failed.intervals.size, 0, 'rotation error must not starve other cleanup');
    console.log('PASS: shared rotation eligibility, failure propagation, and orientation rollback acknowledgment');
}
if (withHomePins) {
    const unavailable = session({homePinsUnavailable: true});
    await unavailable.context.rpc.exports.init();
    assert.ok(unavailable.logs.some(line => line.startsWith('GXR_CURVATURE_HOME_PINS_UNAVAILABLE')));
    assert.ok(!unavailable.logs.some(line => line.startsWith('GXR_CURVATURE_FATAL')));
    [...unavailable.timers.values()][0].cb();
    assert.equal(unavailable.attached(), 1, 'unsupported Home hooks cannot prevent existing window controls');
    unavailable.context.rpc.exports.onFridaStdin('stop');
    unavailable.restored(); unavailable.restoreRotation(); unavailable.restoreBoundary();
    unavailable.context.pollAgent();
    assert.equal(unavailable.intervals.size, 0);
    console.log('PASS: Home cleanup gates detach; unavailable Home APIs preserve existing controls');
}
