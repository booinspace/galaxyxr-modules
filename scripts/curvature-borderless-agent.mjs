// Home Space rim and hover-caption hooks share the window runtime's Java bridge.
// Caption backgrounds are cast to Android View before visibility calls.
export function installBorderless(Java, fail, CaptionVisibility, initiallyEnabled = true, rotationController = null) {
    function report(message) {
        console.log(message);
        if (message.startsWith('GXR_BORDERLESS_FATAL ')) fail(new Error(message));
    }
    const TASK_NAME = /^task-[0-9]+$/;
    const tracked = new Map();
    const hooks = [];
    const captions = [];
    let stopped = false;
    let restored = false;
    let suppressed = 0;
    let hidden = 0;
    let enabled = initiallyEnabled;
    let rimRestoreError = null;
    let setRim;

    function updateRims() {
        const Updates = Java.use('android.graphics.CPM$NodeUpdates');
        for (const record of tracked.values()) {
            const updates = Updates.$new();
            try {
                setRim.call(record.graph, updates, !enabled && record.desired);
                updates.apply();
            } finally { updates.close(); }
        }
    }

    function setEnabled(value) {
        if (stopped || enabled === value) return;
        enabled = value;
        updateRims();
        for (const ticket of captions) ticket.setEnabled(value);
    }

    function stop(reason) {
        if (stopped) return;
        stopped = true;
        Java.perform(() => {
            enabled = false;
            try { updateRims(); }
            catch (error) {
                rimRestoreError = error;
                report('GXR_BORDERLESS_RESTORE_ERROR ' + String(error));
            }
            for (const hook of hooks) hook.implementation = null;
            hooks.length = 0;
            for (const record of tracked.values()) record.graph.$dispose();
            tracked.clear();
            for (const ticket of captions) {
                try { ticket.close(); }
                catch (error) { report('GXR_BORDERLESS_RESTORE_ERROR ' + String(error)); }
            }
        });
    }

    function captionFor(view) {
        for (let i = captions.length - 1; i >= 0; i--) {
            if (captions[i].isCollected()) captions.splice(i, 1)[0].$dispose();
            else if (captions[i].owns(view)) return captions[i];
        }
        const ticket = Java.retain(CaptionVisibility.$new(view));
        captions.push(ticket);
        return ticket;
    }

    try {
        const viewClass = Java.use('android.view.View');
        const subgraph = Java.use('com.android.systemui.xr.spatial.impl.SpaceFlingerCpmSubgraph');
        const initialize = subgraph.initialize.overload(
            'android.graphics.CPM$NodeUpdates', 'java.lang.String', 'int');
        setRim = subgraph.setMainWindowRimEnabled.overload(
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

        initialize.implementation = function (updates, name, order) {
            const result = initialize.call(this, updates, name, order);
            if (!stopped && TASK_NAME.test(String(name))) {
                try {
                    const node = this.getWindowNode();
                    const key = String(node.getNativeHandle());
                    if (tracked.has(key)) tracked.get(key).graph.$dispose();
                    if (tracked.size >= 128) throw new Error('Too many window rim records');
                    tracked.set(key, {graph: Java.retain(this), desired: true});
                    if (enabled) {
                        updates.disablePanelBorderRim(node);
                        if (++suppressed === 1) report('GXR_BORDERLESS_SUPPRESSED first task window rim');
                    }
                } catch (error) {
                    report('GXR_BORDERLESS_FATAL ' + String(error));
                }
            }
            return result;
        };
        hooks.push(initialize);

        setRim.implementation = function (updates, desired) {
            try {
                if (!stopped && tracked.has(String(this.getWindowNode().getNativeHandle()))) {
                    tracked.get(String(this.getWindowNode().getNativeHandle())).desired = desired;
                    return setRim.call(this, updates, !enabled && desired);
                }
            } catch (error) {
                report('GXR_BORDERLESS_FATAL ' + String(error));
            }
            return setRim.call(this, updates, desired);
        };
        hooks.push(setRim);

        release.implementation = function (updates) {
            try {
                const key = String(this.getWindowNode().getNativeHandle());
                if (tracked.has(key)) tracked.get(key).graph.$dispose();
                tracked.delete(key);
            }
            catch (error) { report('GXR_BORDERLESS_ERROR ' + String(error)); }
            return release.call(this, updates);
        };
        hooks.push(release);

        setupCaption.implementation = function (root, params) {
            const result = setupCaption.call(this, root, params);
            if (!stopped) {
                try {
                    if (rotationController !== null) rotationController.bindWindow(this, root);
                    const background = Java.cast(root.requireViewById(backgroundId), viewClass);
                    captionFor(background).setEnabled(enabled); // INVISIBLE retains the drag layout.
                    if (enabled && ++hidden === 1) report('GXR_BORDERLESS_CAPTION_HIDDEN first caption');
                } catch (error) {
                    report('GXR_BORDERLESS_FATAL ' + String(error));
                }
            }
            return result;
        };
        hooks.push(setupCaption);

        dispatchHover.implementation = function (event) {
            if (!stopped && enabled && this.getId() === captionId &&
                String(this.getClass().getName()) === 'com.android.wm.shell.windowdecor.WindowDecorLinearLayout') {
                try {
                    const background = Java.cast(this.requireViewById(backgroundId), viewClass);
                    captionFor(background).hover(event.getActionMasked() === motion.ACTION_HOVER_EXIT.value);
                } catch (error) {
                    report('GXR_BORDERLESS_FATAL ' + String(error));
                }
            }
            return dispatchHover.call(this, event);
        };
        hooks.push(dispatchHover);

        // The shared monotonic supervisor owns expiry; wall time advances during sleep.
        report('GXR_BORDERLESS_READY');
        return {
            setEnabled,
            pulse() {
                for (const ticket of captions) {
                    const error = ticket.getLastError();
                    if (error !== null) throw new Error('Caption visibility: ' + error);
                }
            },
            stop() { stop('curvature supervisor stopped'); },
            isStopped() {
                if (!stopped || restored) return restored;
                if (rimRestoreError !== null) return false;
                let pending = false;
                for (const ticket of captions) {
                    if (!ticket.isRestored()) { ticket.close(); pending = true; }
                }
                if (!pending) {
                    for (const ticket of captions) ticket.$dispose();
                    captions.length = 0;
                    restored = true;
                    report('GXR_BORDERLESS_STOPPED curvature supervisor stopped');
                }
                return restored;
            },
        };
    } catch (error) {
        for (const hook of hooks) hook.implementation = null;
        report('GXR_BORDERLESS_FATAL ' + String(error.stack || error));
        throw error;
    }
}
