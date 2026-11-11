import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('../modules/borderless-windows/agent.js', import.meta.url), 'utf8')
    .replace("import Java from 'frida-java-bridge';", '');

test('hides only task window rims and restores the original hooks on stop', () => {
    const calls = [];
    const logs = [];
    const timers = new Map();
    const method = original => ({
        implementation: null,
        call(receiver, ...args) { return original.apply(receiver, args); },
    });
    const initialize = method(function (updates, name) {
        calls.push(['initialize', String(name)]);
        updates.enablePanelBorderRim(this.getWindowNode());
    });
    const setRim = method(function (updates, enabled) {
        calls.push(['setRim', enabled]);
    });
    const release = method(function () { calls.push(['release']); });
    const setupCaption = method(function () { calls.push(['setupCaption']); });
    const dispatchHover = method(function () { calls.push(['hover']); return false; });
    const subgraph = {
        initialize: {overload: () => initialize},
        setMainWindowRimEnabled: {overload: () => setRim},
        release: {overload: () => release},
    };
    const classes = {
        'com.android.systemui.xr.spatial.impl.SpaceFlingerCpmSubgraph': subgraph,
        'com.android.wm.shell.windowdecor.XrCaptionWindowDecoration': {
            setupRootView: {overload: () => setupCaption},
        },
        'android.view.ViewGroup': {dispatchHoverEvent: {overload: () => dispatchHover}},
        'com.android.systemui.R$id': {caption: {value: 10}, caption_background: {value: 11}},
        'android.view.MotionEvent': {ACTION_HOVER_EXIT: {value: 10}},
        'java.lang.System': {identityHashCode: () => 42},
        'java.lang.ref.WeakReference': {$new: view => ({get: () => view})},
    };
    const rpc = {};
    runInNewContext(source, {
        Java: {
            perform: callback => callback(),
            scheduleOnMainThread: callback => callback(),
            retain: view => view,
            use: name => classes[name],
        },
        rpc,
        console: {log: line => logs.push(line)},
        setInterval: () => 1,
        setTimeout: callback => { const id = timers.size + 1; timers.set(id, callback); return id; },
        clearTimeout: id => timers.delete(id),
    });
    const updates = {
        enablePanelBorderRim: () => calls.push(['enable']),
        disablePanelBorderRim: () => calls.push(['disable']),
    };
    const task = id => ({getWindowNode: () => ({getNativeHandle: () => id})});
    const ordinary = task(42);
    const system = task(99);

    initialize.implementation.call(ordinary, updates, 'task-42', 100);
    assert.deepEqual(calls.slice(-2), [['enable'], ['disable']]);
    setRim.implementation.call(ordinary, updates, true);
    assert.deepEqual(calls.at(-1), ['setRim', false]);

    initialize.implementation.call(system, updates, 'overlay-panel', 100);
    assert.deepEqual(calls.at(-1), ['enable']);
    setRim.implementation.call(system, updates, true);
    assert.deepEqual(calls.at(-1), ['setRim', true]);

    release.implementation.call(ordinary, updates);
    setRim.implementation.call(ordinary, updates, true);
    assert.deepEqual(calls.at(-1), ['setRim', true]);

    const background = {visibility: 0, setVisibility(value) { this.visibility = value; }};
    const caption = {
        getClass: () => ({getName: () => 'com.android.wm.shell.windowdecor.WindowDecorLinearLayout'}),
        getId: () => 10,
        requireViewById: id => { assert.equal(id, 11); return background; },
    };
    setupCaption.implementation.call({}, caption, {});
    assert.equal(background.visibility, 4);
    dispatchHover.implementation.call(caption, {getActionMasked: () => 9});
    assert.equal(background.visibility, 0);
    dispatchHover.implementation.call(caption, {getActionMasked: () => 10});
    assert.equal(background.visibility, 0);
    for (const callback of timers.values()) callback();
    assert.equal(background.visibility, 4);
    dispatchHover.implementation.call(caption, {getActionMasked: () => 9});
    assert.equal(background.visibility, 0);
    const other = {...caption, getId: () => 99};
    dispatchHover.implementation.call(other, {getActionMasked: () => 10});
    assert.equal(background.visibility, 0);

    rpc.exports.onFridaStdin('stop');
    assert.equal(initialize.implementation, null);
    assert.equal(setRim.implementation, null);
    assert.equal(release.implementation, null);
    assert.equal(setupCaption.implementation, null);
    assert.equal(dispatchHover.implementation, null);
    assert.equal(background.visibility, 0);
    assert.ok(logs.some(line => line.startsWith('GXR_BORDERLESS_SUPPRESSED')));
    assert.ok(logs.some(line => line.startsWith('GXR_BORDERLESS_CAPTION_HIDDEN')));
});
