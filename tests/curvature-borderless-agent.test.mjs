import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('../scripts/curvature-borderless-agent.mjs', import.meta.url), 'utf8')
    .replace('export function', 'function');

function fixture() {
    const calls = [], logs = [], failures = [], mainQueue = [];
    const timers = new Map(), intervals = new Map();
    let clock = 0, timerId = 0;
    const method = original => ({implementation: null,
        call(receiver, ...args) { return original.apply(receiver, args); }});
    const initialize = method(function (updates) { updates.enablePanelBorderRim(this.getWindowNode()); });
    const setRim = method(function (_updates, enabled) { calls.push(['rim', enabled]); });
    const release = method(function () { calls.push(['release']); });
    const setupCaption = method(function () { calls.push(['caption']); });
    const dispatchHover = method(function () { calls.push(['stock hover']); return false; });
    const viewClass = {};
    const classes = {
        'android.view.View': viewClass,
        'com.android.systemui.xr.spatial.impl.SpaceFlingerCpmSubgraph': {
            initialize: {overload: () => initialize},
            setMainWindowRimEnabled: {overload: () => setRim},
            release: {overload: () => release},
        },
        'com.android.wm.shell.windowdecor.XrCaptionWindowDecoration': {
            setupRootView: {overload: () => setupCaption},
        },
        'android.view.ViewGroup': {dispatchHoverEvent: {overload: () => dispatchHover}},
        'com.android.systemui.R$id': {caption: {value: 10}, caption_background: {value: 11}},
        'android.view.MotionEvent': {ACTION_HOVER_EXIT: {value: 10}},
        'java.lang.System': {identityHashCode: () => 42},
        'java.lang.ref.WeakReference': {$new: view => ({get: () => ({view})})},
    };
    const Java = {
        use(name) { assert.ok(classes[name], `unexpected class ${name}`); return classes[name]; },
        cast(wrapper, type) { assert.equal(type, viewClass); return wrapper.view; },
        perform: callback => callback(),
        scheduleOnMainThread: callback => mainQueue.push(callback),
        retain: view => view,
    };
    const context = {
        Java, console: {log: line => logs.push(line)}, Date: {now: () => clock},
        setInterval(callback) { const id = ++timerId; intervals.set(id, callback); return id; },
        clearInterval: id => intervals.delete(id),
        setTimeout(callback) {
            const id = ++timerId;
            timers.set(id, () => { timers.delete(id); callback(); });
            return id;
        },
        clearTimeout: id => timers.delete(id),
        fail(error) { failures.push(error); context.handle?.stop(); },
    };
    runInNewContext(source + '\nhandle = installBorderless(Java, fail);', context);
    const updates = {
        enablePanelBorderRim: () => calls.push(['stock rim']),
        disablePanelBorderRim: () => calls.push(['hide rim']),
    };
    const background = {visibility: 0, setVisibility(value) { this.visibility = value; }};
    const caption = {
        getClass: () => ({getName: () => 'com.android.wm.shell.windowdecor.WindowDecorLinearLayout'}),
        getId: () => 10,
        requireViewById(id) { assert.equal(id, 11); return {view: background}; },
    };
    return {context, calls, logs, failures, timers, intervals, updates, background, caption,
        initialize, setRim, release, setupCaption, dispatchHover,
        clock(value) { clock = value; },
        flushMain() { while (mainQueue.length) mainQueue.shift()(); },
    };
}

test('restored task rims and hover pill retain stock event handling and stop acknowledgment', () => {
    const f = fixture(), handle = f.context.handle;
    const task = id => ({getWindowNode: () => ({getNativeHandle: () => id})});
    const ordinary = task(42), system = task(99);
    f.initialize.implementation.call(ordinary, f.updates, 'task-42', 0);
    f.setRim.implementation.call(ordinary, f.updates, true);
    f.initialize.implementation.call(system, f.updates, 'overlay-panel', 0);
    f.setRim.implementation.call(system, f.updates, true);
    assert.deepEqual(f.calls, [['stock rim'], ['hide rim'], ['rim', false], ['stock rim'], ['rim', true]]);
    f.release.implementation.call(ordinary, f.updates);
    f.setRim.implementation.call(ordinary, f.updates, true);
    assert.deepEqual(f.calls.at(-1), ['rim', true]);

    f.setupCaption.implementation.call({}, f.caption, {});
    assert.equal(f.background.visibility, 4);
    assert.equal(f.dispatchHover.implementation.call(f.caption, {getActionMasked: () => 9}), false);
    assert.equal(f.background.visibility, 0);
    f.dispatchHover.implementation.call(f.caption, {getActionMasked: () => 10});
    assert.equal(f.background.visibility, 0);
    for (const callback of f.timers.values()) callback();
    f.flushMain();
    assert.equal(f.background.visibility, 4);
    f.dispatchHover.implementation.call(f.caption, {getActionMasked: () => 10});
    f.dispatchHover.implementation.call(f.caption, {getActionMasked: () => 9});
    assert.equal(f.timers.size, 0);
    assert.equal(f.background.visibility, 0);
    f.dispatchHover.implementation.call({...f.caption, getId: () => 99}, {getActionMasked: () => 10});
    assert.equal(f.timers.size, 0);

    f.background.visibility = 4;
    handle.stop();
    handle.stop();
    assert.equal(handle.isStopped(), false, 'must wait for UI restoration');
    assert.equal(f.intervals.size, 0);
    f.flushMain();
    assert.equal(handle.isStopped(), true);
    assert.equal(f.background.visibility, 0);
    for (const hook of [f.initialize, f.setRim, f.release, f.setupCaption, f.dispatchHover]) {
        assert.equal(hook.implementation, null);
    }
    assert.equal(f.logs.filter(line => line.startsWith('GXR_BORDERLESS_STOPPED')).length, 1);
    assert.deepEqual(f.failures, []);
});

test('supervisor pulses keep the restored hooks alive; expiry stops the combined agent', () => {
    const f = fixture(), watchdog = [...f.intervals.values()][0];
    f.clock(4000);
    f.context.handle.pulse();
    f.clock(8000);
    watchdog();
    assert.deepEqual(f.failures, []);
    f.clock(9001);
    watchdog();
    assert.match(String(f.failures[0]), /supervisor timeout/);
    f.flushMain();
    assert.equal(f.context.handle.isStopped(), true);
});

test('caption failure reaches Curvature fail handler and removes all owned hooks', () => {
    const f = fixture();
    f.setupCaption.implementation.call({}, {requireViewById() { throw new Error('missing caption'); }}, {});
    assert.match(String(f.failures[0]), /missing caption/);
    f.flushMain();
    assert.equal(f.context.handle.isStopped(), true);
    assert.equal(f.dispatchHover.implementation, null);
});
