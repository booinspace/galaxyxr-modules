import test from 'node:test';
import assert from 'node:assert/strict';
import {installBorderless} from '../scripts/curvature-borderless-agent.mjs';

function fixture(withRotation = true) {
    const hooks = [], discoveries = [], bound = [], failures = [];
    const method = () => {
        const hook = {implementation: null, call() {}}; hooks.push(hook);
        return {overload: () => hook};
    };
    const classes = {
        'android.view.View': {},
        'android.view.ViewGroup': {dispatchHoverEvent: method()},
        'android.view.MotionEvent': {ACTION_HOVER_EXIT: {value: 10}},
        'com.android.systemui.xr.spatial.impl.SpaceFlingerCpmSubgraph': {
            initialize: method(), setMainWindowRimEnabled: method(), release: method()},
        'com.android.wm.shell.windowdecor.XrCaptionWindowDecoration': {setupRootView: method()},
        'com.android.systemui.R$id': {caption: {value: 1}, caption_background: {value: 2}},
        'android.graphics.CPM$NodeUpdates': {},
    };
    const Java = {use(name) { assert.ok(classes[name], name); return classes[name]; }, perform: callback => callback(),
        choose(name, callbacks) {
            assert.equal(name, 'com.android.wm.shell.windowdecor.XrCaptionWindowDecorDirector'); discoveries.push(callbacks);
        }};
    const result = installBorderless(Java, error => failures.push(error), {}, true,
        withRotation ? {bindExistingWindows: director => bound.push(director)} : null);
    return {result, hooks, discoveries, bound, failures};
}

test('startup discovers existing captions without waiting for a new window or menu', () => {
    const f = fixture(), director = {};
    assert.equal(f.discoveries.length, 1);
    f.discoveries[0].onMatch(director); f.discoveries[0].onComplete();
    assert.deepEqual(f.bound, [director]); assert.deepEqual(f.failures, []);
    f.result.stop(); assert.equal(f.result.isStopped(), true);
    assert.ok(f.hooks.every(hook => hook.implementation === null));
});

test('shutdown waits for heap discovery and prevents late caption bindings', () => {
    const f = fixture();
    f.result.stop(); assert.equal(f.result.isStopped(), false);
    f.discoveries[0].onMatch({}); f.discoveries[0].onComplete();
    assert.deepEqual(f.bound, []); assert.equal(f.result.isStopped(), true);
});

test('standalone borderless does not enumerate rotation captions', () => {
    const f = fixture(false);
    assert.deepEqual(f.discoveries, []); f.result.stop(); assert.equal(f.result.isStopped(), true);
});
