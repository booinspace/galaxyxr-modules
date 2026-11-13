import test from 'node:test';
import assert from 'node:assert/strict';
import {HOME_PIN_LIMIT, installHomePins} from '../scripts/curvature-home-pins-agent.mjs';

function fixture({existing = [], delayedDiscovery = false, missingClass = false} = {}) {
    const queue = [], hooks = [], calls = [];
    let permitted = true, taskhome = true, failLayout = false, discovery;
    const method = callback => {
        const result = {implementation: null, call: (receiver, ...args) => callback.apply(receiver, args)};
        hooks.push(result);
        return {overload: () => result};
    };
    const First = {
        $className: 'com.android.systemui.xr.launcher.allapps.ui.view.FirstPageGridLayoutManager',
        onLayoutChildren: method(function (...args) { calls.push(['stock-layout', this, ...args]); return 'stock'; }),
        canScrollVertically: method(() => false),
        onInterceptFocusSearch: method(() => 'stock-focus'),
    };
    const Grid = {
        onLayoutChildren: method(function (...args) {
            assert.equal(this.direct, true, 'superclass call must bypass virtual dispatch');
            if (failLayout) throw new Error('layout failed');
            calls.push(['grid-layout', this.owner, ...args]);
            return 'grid';
        }),
        canScrollVertically: method(function () {
            assert.equal(this.direct, true, 'scroll superclass call must be nonvirtual');
            return true;
        }),
    };
    const limit = method(function () { return this.stock; });
    const cachedLimit = method(function () { return this.stock; });
    const map = new Map();
    let disposed = false;
    const classes = {
        [First.$className]: First,
        'androidx.recyclerview.widget.GridLayoutManager': Grid,
        'androidx.recyclerview.widget.RecyclerView$LayoutManager': {},
        'com.android.systemui.xr.pinning.data.PinningAppsRepositoryImpl': {getLimit: limit},
        'com.android.systemui.xr.pinning.PinningAppsImpl': {getPinnedAppsLimit: cachedLimit},
        'com.android.xr.flags.Flags': {enableTaskhome: () => taskhome},
        'java.lang.Integer': {valueOf: value => ({intValue: () => value})},
        'java.util.ArrayList': {$new: values => ({size: () => values.length, get: i => values[i]})},
        'java.util.WeakHashMap': {$new: () => ({
            put: (key, value) => map.set(key, value), keySet: () => [...map.keys()],
            containsKey: key => map.has(key), get: key => map.get(key) ?? null,
            clear: () => map.clear(), $dispose: () => { disposed = true; },
        })},
    };
    const Java = {
        use(name) {
            if (missingClass && name.endsWith('Flags')) throw new Error('Missing class');
            assert.ok(classes[name], name);
            return classes[name];
        },
        retain: value => value, cast: value => value, perform: callback => callback(),
        scheduleOnMainThread: callback => queue.push(callback),
        choose(name, callbacks) {
            assert.equal(name, First.$className);
            discovery = () => {
                for (const value of existing) callbacks.onMatch(value);
                callbacks.onComplete();
            };
            if (!delayedDiscovery) discovery();
        },
    };
    return {
        Java, hooks, calls, First, limit: limit.overload(), cachedLimit: cachedLimit.overload(),
        layout: First.onLayoutChildren.overload(), scroll: First.canScrollVertically.overload(),
        focus: First.onInterceptFocusSearch.overload(),
        install: () => installHomePins(Java, () => permitted),
        flush: () => { while (queue.length) queue.shift()(); },
        discover: () => discovery(), disposed: () => disposed,
        permit: value => { permitted = value; }, taskhome: value => { taskhome = value; },
        failLayout: () => { failLayout = true; },
    };
}

function manager(count, clipChildren = false, clipToPadding = false) {
    const view = {
        getClipChildren: () => clipChildren, getClipToPadding: () => clipToPadding,
        setClipChildren: value => { clipChildren = value; }, setClipToPadding: value => { clipToPadding = value; },
    };
    const value = {count, requests: 0, positions: [], getItemCount() { return this.count; },
        mRecyclerView: {value: view},
        requestLayout() { this.requests++; }, scrollToPosition(i) { this.positions.push(i); }};
    value.$super = {direct: true, owner: value};
    return value;
}

test('raises live and cached home limits without changing taskbar or an existing higher limit', () => {
    const f = fixture(); f.install();
    for (const method of [f.limit, f.cachedLimit]) {
        assert.equal(method.implementation.call({stock: 10}), HOME_PIN_LIMIT);
        assert.equal(method.implementation.call({stock: 100}), 100);
        f.taskhome(false);
        assert.equal(method.implementation.call({stock: 5}), 5);
        f.taskhome(true); f.permit(false);
        assert.equal(method.implementation.call({stock: 10}), 10);
        f.permit(true);
    }
});

test('retains exact stock layout, focus and scrolling behavior for zero through ten pins', () => {
    const f = fixture(); f.install();
    for (let count = 0; count <= 10; count++) {
        const m = manager(count), recycler = {}, state = {count};
        assert.equal(f.layout.implementation.call(m, recycler, state), 'stock');
        assert.deepEqual(f.calls.at(-1), ['stock-layout', m, recycler, state]);
        assert.equal(f.scroll.implementation.call(m), false);
        assert.equal(f.focus.implementation.call(m, {}, 130), 'stock-focus');
    }
    assert.ok(f.calls.every(call => call[0] === 'stock-layout'));
});

test('overflow uses the direct superclass grid and scroll implementation, with normal focus search', () => {
    const f = fixture(); const controller = f.install();
    for (const count of [11, 15, 50]) {
        const m = manager(count), recycler = {}, state = {count};
        assert.equal(f.layout.implementation.call(m, recycler, state), 'grid');
        assert.deepEqual(f.calls.at(-1), ['grid-layout', m, recycler, state]);
        assert.equal(f.scroll.implementation.call(m), true);
        assert.equal(f.focus.implementation.call(m, {}, 130), null);
    }
    assert.equal(controller.getDiagnostics().overflowLayouts, 3);
    assert.equal(controller.getDiagnostics().scrollQueries, 3);
});

test('losing the supervisor lease or taskhome flag returns overflow to stock behavior', () => {
    const f = fixture(); f.install(); const m = manager(20);
    for (const revoke of [() => f.permit(false), () => { f.permit(true); f.taskhome(false); }]) {
        revoke();
        assert.equal(f.layout.implementation.call(m, {}, {}), 'stock');
        assert.equal(f.scroll.implementation.call(m), false);
        assert.equal(f.focus.implementation.call(m, {}, 130), 'stock-focus');
    }
});

test('scrolling rows clip inside Home and restore each original flag on reduction or stop', () => {
    for (const children of [false, true]) for (const padding of [false, true]) {
        const m = manager(15, children, padding), f = fixture({existing: [m]});
        const controller = f.install(); f.flush();
        const view = m.mRecyclerView.value;
        for (let n = 0; n < 2; n++) {
            f.layout.implementation.call(m, {}, {});
            assert.equal(view.getClipChildren(), true);
            assert.equal(view.getClipToPadding(), true);
        }
        m.count = 10; f.layout.implementation.call(m, {}, {});
        assert.equal(view.getClipChildren(), children);
        assert.equal(view.getClipToPadding(), padding);
        m.count = 50; f.layout.implementation.call(m, {}, {});
        controller.stop(); f.flush();
        assert.equal(controller.isRestored(), true);
        assert.equal(view.getClipChildren(), children);
        assert.equal(view.getClipToPadding(), padding);
    }
});

test('lease loss restores clipping and detached managers do not write a view', () => {
    const m = manager(15), f = fixture(); const controller = f.install();
    f.layout.implementation.call(m, {}, {});
    f.permit(false); f.layout.implementation.call(m, {}, {});
    assert.equal(m.mRecyclerView.value.getClipChildren(), false);
    assert.equal(m.mRecyclerView.value.getClipToPadding(), false);
    f.permit(true); m.mRecyclerView.value = null;
    assert.doesNotThrow(() => f.layout.implementation.call(m, {}, {}));
    controller.stop(); f.flush(); assert.equal(controller.isRestored(), true);
});

test('reflows existing Home views on the UI thread and returns to stock after reducing to ten', () => {
    const m = manager(20), f = fixture({existing: [m]}); f.install();
    assert.equal(m.requests, 0); f.flush(); assert.equal(m.requests, 1);
    assert.equal(f.layout.implementation.call(m, {}, {}), 'grid');
    m.count = 10;
    assert.equal(f.layout.implementation.call(m, {}, {}), 'stock');
    assert.equal(f.scroll.implementation.call(m), false);
});

test('cleanup acknowledgment waits for UI restoration and removes all hooks', () => {
    const m = manager(20);
    const f = fixture({existing: [m]}); const controller = f.install(); f.flush();
    controller.stop(); controller.stop();
    assert.equal(controller.isRestored(), false);
    assert.equal(f.limit.implementation.call({stock: 10}), 10);
    f.flush();
    assert.equal(controller.isRestored(), true);
    assert.ok(f.hooks.every(hook => hook.implementation === null));
    assert.deepEqual(m.positions, [0]); assert.equal(m.requests, 2);
    controller.dispose(); assert.equal(f.disposed(), true);
});

test('an overflow layout error falls back to stock and stops only the pin hooks', () => {
    const f = fixture(); const controller = f.install(); f.failLayout();
    assert.equal(f.layout.implementation.call(manager(20), {}, {}), 'stock');
    assert.equal(controller.getDiagnostics().enabled, false);
    assert.match(controller.getDiagnostics().error, /layout failed/);
    assert.equal(controller.isRestored(), false); f.flush();
    assert.equal(controller.isRestored(), true);
    assert.ok(f.hooks.every(hook => hook.implementation === null));
});

test('a missing AZJ2 API fails before any method is hooked', () => {
    const f = fixture({missingClass: true});
    assert.throws(f.install, /Missing class/);
    assert.ok(f.hooks.every(hook => hook.implementation === null));
});

test('stop during heap discovery does not retain late views and waits for discovery completion', () => {
    const m = manager(20), f = fixture({existing: [m], delayedDiscovery: true});
    const controller = f.install(); controller.stop(); f.flush();
    assert.equal(controller.isRestored(), false);
    f.discover(); assert.equal(controller.isRestored(), true);
    assert.equal(m.requests, 0); assert.deepEqual(m.positions, []);
});

test('a failed UI restoration never acknowledges stock state', () => {
    const m = manager(20), f = fixture({existing: [m]});
    const controller = f.install(); f.flush();
    m.requestLayout = () => { throw new Error('view unavailable'); };
    controller.stop(); f.flush();
    assert.equal(controller.isRestored(), false);
    assert.match(controller.getDiagnostics().error, /view unavailable/);
    assert.ok(f.hooks.every(hook => hook.implementation === null));
});
