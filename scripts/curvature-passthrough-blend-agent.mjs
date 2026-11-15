/** Reuse the stock Quick Settings dimmer row; the existing injector owns all hooks. */
export function installPassthroughBlend(Java, factory, permitted, report) {
    let controller = null, stopped = false, retained = [], hooks = [];
    let error = '';
    function stop() {
        stopped = true;
        for (const hook of hooks) hook.implementation = null;
        hooks = [];
        if (controller !== null) controller.close();
    }
    function fail(failure) {
        error = String(failure.stack || failure);
        stop();
        report('PASSTHROUGH_BLEND_UNAVAILABLE', {error});
    }
    function bind() {
        const manager = Java.use('com.android.systemui.xr.wm.shell.mixedreality.MixedRealityStateManager');
        const compute = manager.computeStates;
        compute.implementation = function (...args) {
            const result = compute.call(this, ...args);
            if (stopped || !permitted() || controller === null) return result;
            try { return controller.states(args[0], result); }
            catch (failure) { fail(failure); return result; }
        };
        hooks.push(compute);
        const element = Java.use('com.android.systemui.xr.qs.ui.QuickSettingsXrElement');
        const resume = element.onResume.overload();
        resume.implementation = function () {
            const result = resume.call(this);
            if (!stopped && controller !== null) {
                try { const view = this.getView(); controller.attach(view.getContentView(), view); }
                catch (failure) { fail(failure); }
            }
            return result;
        };
        hooks.push(resume);
        const destroy = element.onDestroy.overload();
        destroy.implementation = function () {
            if (!stopped && controller !== null) {
                try { controller.detach(this.getView().getContentView()); }
                catch (failure) { fail(failure); }
            }
            return destroy.call(this);
        };
        hooks.push(destroy);
        Java.choose('com.android.systemui.xr.qs.ui.QuickSettingsXrElement', {
            onMatch(value) {
                if (!stopped && controller !== null) {
                    const view = value.getView(); controller.attach(view.getContentView(), view);
                }
            },
            onComplete() { report('PASSTHROUGH_BLEND_READY', {nativeQuickSettings: true}); },
        });
    }
    try {
        Java.choose('com.android.systemui.xr.wm.shell.mixedreality.PassthroughDimmerManager', {
            onMatch(value) {
                if (!stopped && retained.length === 0) retained.push(Java.retain(value));
                return 'stop';
            },
            onComplete() {
                try {
                    if (stopped) return;
                    if (retained.length !== 1) throw new Error('Native passthrough manager unavailable');
                    const app = Java.use('android.app.ActivityThread').currentApplication();
                    controller = Java.retain(factory.use('local.gxr.controls.PassthroughBlend')
                        .$new(app.getApplicationContext(), retained[0]));
                    bind();
                } catch (failure) { fail(failure); }
                finally { for (const value of retained) value.$dispose(); retained = []; }
            },
        });
    } catch (failure) { fail(failure); }
    return {
        pulse() {
            if (stopped || controller === null) return;
            controller.pulse();
            const problem = String(controller.getError());
            if (problem !== '') fail(new Error(problem));
        },
        stop,
        isStopped() { return controller === null || controller.isStopped(); },
        status() { return {stopped, percent: controller === null ? null : controller.getPercent(), panelHeightPx: controller === null ? null : controller.getPanelHeightPx(), layout: controller === null ? '' : String(controller.getLayout()), error}; },
    };
}
