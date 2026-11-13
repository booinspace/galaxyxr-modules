export const HOME_PIN_LIMIT = 50;

// AZJ2's stock manager draws at most 5 + 5 items and refuses vertical scrolling.
export function installHomePins(Java, permitted) {
    const First = Java.use('com.android.systemui.xr.launcher.allapps.ui.view.FirstPageGridLayoutManager');
    const Grid = Java.use('androidx.recyclerview.widget.GridLayoutManager');
    const LayoutManager = Java.use('androidx.recyclerview.widget.RecyclerView$LayoutManager');
    const Repository = Java.use('com.android.systemui.xr.pinning.data.PinningAppsRepositoryImpl');
    const Pinning = Java.use('com.android.systemui.xr.pinning.PinningAppsImpl');
    const Flags = Java.use('com.android.xr.flags.Flags');
    const IntegerType = Java.use('java.lang.Integer');
    const ArrayList = Java.use('java.util.ArrayList');
    const managers = Java.retain(Java.use('java.util.WeakHashMap').$new());
    const signature = ['androidx.recyclerview.widget.RecyclerView$Recycler',
        'androidx.recyclerview.widget.RecyclerView$State'];
    const layout = First.onLayoutChildren.overload(...signature);
    const baseLayout = Grid.onLayoutChildren.overload(...signature);
    const scroll = First.canScrollVertically.overload();
    const baseScroll = Grid.canScrollVertically.overload();
    const focus = First.onInterceptFocusSearch.overload('android.view.View', 'int');
    const limits = [Repository.getLimit.overload(), Pinning.getPinnedAppsLimit.overload()];
    const hooks = [...limits, layout, scroll, focus];
    let enabled = false, stopping = false, restored = false, discoveryDone = false;
    let layouts = 0, overflowLayouts = 0, scrollQueries = 0, lastError = null;
    const active = () => enabled && permitted() && Flags.enableTaskhome();
    const overflow = manager => active() && manager.getItemCount() > 10;

    function eachManager(callback) {
        const snapshot = ArrayList.$new(managers.keySet());
        for (let i = 0; i < snapshot.size(); i++) callback(Java.cast(snapshot.get(i), First));
    }
    function remember(manager) {
        if (!managers.containsKey(manager)) managers.put(manager, IntegerType.valueOf(-1));
    }
    function clipOverflow(manager, enabled) {
        const saved = managers.get(manager);
        if (saved === null) return;
        let flags = Number(Java.cast(saved, IntegerType).intValue());
        if (flags < 0 && !enabled) return;
        const view = Java.cast(manager, LayoutManager).mRecyclerView.value;
        if (view === null) return;
        if (flags < 0) {
            flags = (view.getClipChildren() ? 1 : 0) | (view.getClipToPadding() ? 2 : 0);
            managers.put(manager, IntegerType.valueOf(flags));
        }
        // Samsung disables clipping for the fixed grid; scrolling rows must stay below the toolbar.
        view.setClipChildren(enabled || (flags & 1) !== 0);
        view.setClipToPadding(enabled || (flags & 2) !== 0);
    }
    function error(value) {
        enabled = false;
        lastError = String(value.stack || value);
        console.log('GXR_HOME_PINS_ERROR ' + lastError);
        stop();
    }
    function stop() {
        if (stopping) return;
        stopping = true;
        enabled = false;
        Java.perform(() => Java.scheduleOnMainThread(() => {
            try {
                for (const hook of hooks) hook.implementation = null;
                eachManager(manager => {
                    clipOverflow(manager, false);
                    manager.scrollToPosition(0);
                    manager.requestLayout();
                });
                managers.clear();
                restored = true;
                console.log('GXR_HOME_PINS_STOPPED');
            } catch (value) {
                lastError = String(value.stack || value);
                console.log('GXR_HOME_PINS_RESTORE_ERROR ' + lastError);
            }
        }));
    }
    try {
        for (const original of limits) {
            original.implementation = function () {
                const stock = original.call(this);
                return active() ? Math.max(stock, HOME_PIN_LIMIT) : stock;
            };
        }
        layout.implementation = function (recycler, state) {
            try {
                if (active()) remember(this);
                layouts++;
                const expanded = state !== null && overflow(this);
                clipOverflow(this, expanded);
                if (expanded) {
                    overflowLayouts++;
                    // A virtual JNI call would re-enter this same final override.
                    return baseLayout.call(this.$super, recycler, state);
                }
            } catch (value) { error(value); }
            return layout.call(this, recycler, state);
        };
        scroll.implementation = function () {
            try {
                if (overflow(this)) {
                    scrollQueries++;
                    return baseScroll.call(this.$super);
                }
            } catch (value) { error(value); }
            return scroll.call(this);
        };
        focus.implementation = function (view, direction) {
            // Let RecyclerView/GridLayoutManager navigate and reveal offscreen rows.
            try { if (overflow(this)) return null; }
            catch (value) { error(value); }
            return focus.call(this, view, direction);
        };
        enabled = true;
        Java.choose(First.$className, {
            onMatch(manager) { if (!stopping) remember(manager); },
            onComplete() {
                discoveryDone = true;
                if (!stopping) Java.scheduleOnMainThread(() => {
                    try { if (active()) eachManager(manager => manager.requestLayout()); }
                    catch (value) { error(value); }
                });
            },
        });
    } catch (value) {
        enabled = false;
        stopping = true;
        for (const hook of hooks) hook.implementation = null;
        managers.clear();
        managers.$dispose();
        throw value;
    }
    console.log('GXR_HOME_PINS_READY ' + JSON.stringify({limit: HOME_PIN_LIMIT, columns: 5}));
    return {
        stop,
        isRestored: () => restored && discoveryDone,
        getDiagnostics: () => ({enabled, limit: HOME_PIN_LIMIT, layouts, overflowLayouts,
            scrollQueries, error: lastError}),
        dispose() { if (restored && discoveryDone) managers.$dispose(); },
    };
}
