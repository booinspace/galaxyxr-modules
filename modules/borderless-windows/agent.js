import Java from 'frida-java-bridge';

const TASK_NAME = /^task-[0-9]+$/;
const tracked = new Set();
const hooks = [];
const captions = [];
const hideTimers = new Map();
let lastPulse = Date.now();
let stopped = false;
let suppressed = 0;
let hidden = 0;

function stop(reason) {
    if (stopped) return;
    stopped = true;
    Java.perform(() => {
        for (const hook of hooks) hook.implementation = null;
        hooks.length = 0;
        tracked.clear();
        for (const timer of hideTimers.values()) clearTimeout(timer);
        hideTimers.clear();
        Java.scheduleOnMainThread(() => {
            for (const ref of captions) {
                const view = ref.get();
                if (view) view.setVisibility(0);
            }
            captions.length = 0;
            console.log('GXR_BORDERLESS_STOPPED ' + reason);
        });
    });
}

rpc.exports = {
    onFridaStdin(line) {
        if (line.trim() === 'pulse') lastPulse = Date.now();
        if (line.trim() === 'stop') stop('requested');
    },
};

Java.perform(() => {
    try {
        const subgraph = Java.use('com.android.systemui.xr.spatial.impl.SpaceFlingerCpmSubgraph');
        const initialize = subgraph.initialize.overload(
            'android.graphics.CPM$NodeUpdates', 'java.lang.String', 'int');
        const setRim = subgraph.setMainWindowRimEnabled.overload(
            'android.graphics.CPM$NodeUpdates', 'boolean');
        const release = subgraph.release.overload('android.graphics.CPM$NodeUpdates');
        const decoration = Java.use('com.android.wm.shell.windowdecor.XrCaptionWindowDecoration');
        const setupCaption = decoration.setupRootView.overload(
            'com.android.wm.shell.windowdecor.WindowDecorLinearLayout',
            'com.android.wm.shell.windowdecor.WindowDecoration$RelayoutParams');
        const viewGroup = Java.use('android.view.ViewGroup');
        const dispatchHover = viewGroup.dispatchHoverEvent.overload('android.view.MotionEvent');
        const ids = Java.use('com.android.systemui.R$id');
        const captionId = ids.caption.value;
        const backgroundId = ids.caption_background.value;
        const motion = Java.use('android.view.MotionEvent');
        const system = Java.use('java.lang.System');
        const weakRef = Java.use('java.lang.ref.WeakReference');

        initialize.implementation = function (updates, name, order) {
            const result = initialize.call(this, updates, name, order);
            if (!stopped && TASK_NAME.test(String(name))) {
                try {
                    const node = this.getWindowNode();
                    tracked.add(String(node.getNativeHandle()));
                    updates.disablePanelBorderRim(node);
                    if (++suppressed === 1) console.log('GXR_BORDERLESS_SUPPRESSED first task window rim');
                } catch (error) {
                    console.log('GXR_BORDERLESS_FATAL ' + String(error));
                }
            }
            return result;
        };
        hooks.push(initialize);

        setRim.implementation = function (updates, enabled) {
            try {
                if (!stopped && tracked.has(String(this.getWindowNode().getNativeHandle()))) {
                    return setRim.call(this, updates, false);
                }
            } catch (error) {
                console.log('GXR_BORDERLESS_FATAL ' + String(error));
            }
            return setRim.call(this, updates, enabled);
        };
        hooks.push(setRim);

        release.implementation = function (updates) {
            try { tracked.delete(String(this.getWindowNode().getNativeHandle())); }
            catch (error) { console.log('GXR_BORDERLESS_ERROR ' + String(error)); }
            return release.call(this, updates);
        };
        hooks.push(release);

        setupCaption.implementation = function (root, params) {
            const result = setupCaption.call(this, root, params);
            if (!stopped) {
                try {
                    const background = root.requireViewById(backgroundId);
                    background.setVisibility(4); // INVISIBLE retains the caption's drag layout.
                    for (let i = captions.length - 1; i >= 0; i--) {
                        if (!captions[i].get()) captions.splice(i, 1);
                    }
                    captions.push(weakRef.$new(background));
                    if (++hidden === 1) console.log('GXR_BORDERLESS_CAPTION_HIDDEN first caption');
                } catch (error) {
                    console.log('GXR_BORDERLESS_FATAL ' + String(error));
                }
            }
            return result;
        };
        hooks.push(setupCaption);

        dispatchHover.implementation = function (event) {
            if (!stopped && this.getId() === captionId &&
                String(this.getClass().getName()) === 'com.android.wm.shell.windowdecor.WindowDecorLinearLayout') {
                try {
                    const background = this.requireViewById(backgroundId);
                    const key = system.identityHashCode(this);
                    const oldTimer = hideTimers.get(key);
                    if (oldTimer) clearTimeout(oldTimer);
                    hideTimers.delete(key);
                    if (event.getActionMasked() === motion.ACTION_HOVER_EXIT.value) {
                        const retained = Java.retain(background);
                        const timer = setTimeout(() => Java.scheduleOnMainThread(() => {
                            if (!stopped && hideTimers.get(key) === timer) {
                                retained.setVisibility(4);
                                hideTimers.delete(key);
                            }
                        }), 500);
                        hideTimers.set(key, timer);
                    } else {
                        background.setVisibility(0);
                    }
                } catch (error) {
                    console.log('GXR_BORDERLESS_FATAL ' + String(error));
                }
            }
            return dispatchHover.call(this, event);
        };
        hooks.push(dispatchHover);

        setInterval(() => {
            if (!stopped && Date.now() - lastPulse > 5000) stop('supervisor timeout');
        }, 1000);
        console.log('GXR_BORDERLESS_READY');
    } catch (error) {
        for (const hook of hooks) hook.implementation = null;
        console.log('GXR_BORDERLESS_FATAL ' + String(error.stack || error));
    }
});
