import {observeHandActions} from './curvature-grab-agent.mjs';

/** One toggle per deliberate left pinch, rearmed only by a tracked release. */
export class PinchToggle {
    constructor(holdMs = 500) {
        if (![0, 500].includes(holdMs)) throw new Error('Unsupported pinch hold');
        this.holdMs = holdMs;
        this.lastFire = -Infinity;
        this.reset();
    }
    reset() {
        this.armed = false;
        this.releasedSince = null;
        this.pinchedSince = null;
        this.lastSample = -Infinity;
    }
    update(data, now) {
        if (data === null || data.hand !== 0) return false;
        const sample = data.sample;
        if (sample === null || sample.pinchActive !== true || !Number.isFinite(now) ||
            !Number.isFinite(sample.sampledAt) || now < sample.sampledAt || now - sample.sampledAt > 100 ||
            !Number.isFinite(sample.pinchStrength) || sample.pinchStrength < 0 || sample.pinchStrength > 1) {
            this.reset();
            return false;
        }
        if (now < this.lastSample || now - this.lastSample > 150) this.reset();
        this.lastSample = now;
        if (sample.pinchStrength <= .35) {
            this.pinchedSince = null;
            if (this.releasedSince === null) this.releasedSince = now;
            if (now - this.releasedSince >= 100) this.armed = true;
            return false;
        }
        this.releasedSince = null;
        if (sample.pinchStrength < .8) {
            this.pinchedSince = null;
            return false;
        }
        if (!this.armed) return false;
        if (this.pinchedSince === null) this.pinchedSince = now;
        if (now - this.pinchedSince < this.holdMs || now - this.lastFire < 750) return false;
        this.armed = false;
        this.pinchedSince = null;
        this.lastFire = now;
        return true;
    }
}

export function parseQuickSettingsCommand(command) {
    const match = /^quick-settings ([01]) (0|500)$/.exec(command);
    return match === null ? null : {enabled: match[1] === '1', holdMs: Number(match[2])};
}

export function installQuickSettingsGesture(Java, factory, permitted, nowMs, report) {
    let enabled = false, holdMs = 500, stopped = false;
    let controller = null, input = null, selected = [], faulted = false, searching = false;
    let lastError = '';
    let gesture = new PinchToggle(holdMs);

    function deactivate() {
        gesture.reset();
        if (input !== null) input.stop();
        input = null;
        if (controller !== null) controller.setEnabled(false);
    }
    function unavailable(error) {
        faulted = true;
        lastError = String(error.stack || error);
        deactivate();
        report('QUICK_SETTINGS_UNAVAILABLE', {error: lastError});
    }
    function activate() {
        if (stopped || faulted || !enabled || input !== null) return;
        if (controller === null) { bindController(); return; }
        try {
            controller.setEnabled(true);
            input = observeHandActions(data => {
                if (!enabled || stopped || faulted) return;
                if (!permitted()) { gesture.reset(); controller.cancel(); return; }
                const now = nowMs();
                if (data !== null && data.hand === 0 &&
                    (data.sample === null || data.sample.pinchActive !== true)) controller.cancel();
                if (gesture.update(data, now)) controller.request();
            }, unavailable, nowMs);
            report('QUICK_SETTINGS_READY', {holdMs});
        } catch (error) { unavailable(error); }
    }

    function bindController() {
        if (searching) return;
        searching = true;
        try {
            const application = Java.use('android.app.ActivityThread').currentApplication();
            if (application === null) throw new Error('SystemUI application unavailable');
            Java.choose('com.android.systemui.xr.launcher.taskbar.model.QuickSettingsButtonViewModel', {
                onMatch(value) {
                    if (!stopped && selected.length === 0) selected.push(Java.retain(value));
                    return 'stop';
                },
                onComplete() {
                    searching = false;
                    if (stopped) return;
                    try {
                        if (selected.length !== 1) throw new Error('Native Quick Settings action is not ready');
                        controller = Java.retain(factory.use('local.gxr.controls.QuickSettingsToggle')
                            .$new(application.getApplicationContext(), selected[0].getToggleQuickSettingsAction()));
                        activate();
                    } catch (error) { unavailable(error); }
                    finally {
                        for (const value of selected) value.$dispose();
                        selected = [];
                    }
                },
            });
        } catch (error) {
            searching = false;
            for (const value of selected) value.$dispose();
            selected = [];
            unavailable(error);
        }
    }

    return {
        configure(value, duration) {
            if (typeof value !== 'boolean' || ![0, 500].includes(duration)) throw new Error('Invalid Quick Settings selection');
            if (stopped || (value === enabled && duration === holdMs)) return;
            deactivate();
            enabled = value;
            holdMs = duration;
            faulted = false;
            lastError = '';
            gesture = new PinchToggle(holdMs);
            activate();
        },
        stop() {
            stopped = true;
            enabled = false;
            deactivate();
            for (const value of selected) value.$dispose();
            selected = [];
            if (controller !== null) { controller.close(); controller.$dispose(); }
            controller = null;
        },
        getDiagnostics() {
            return {enabled, holdMs, ready: input !== null,
                requests: controller === null ? 0 : controller.getRequests(),
                error: lastError || (controller === null ? '' : String(controller.getError()))};
        },
    };
}
