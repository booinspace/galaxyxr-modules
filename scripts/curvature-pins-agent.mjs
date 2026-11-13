import {readHandActionEvent} from './curvature-grab-agent.mjs';
import {installPinnedScrim} from './curvature-pins-scrim.mjs';

// Exact AZJ2 PoseActionState layout consumed by the legacy eye-input path, read-only.
export function readEyePose(output) {
    if (output.isNull() || output.add(0x55).readU8() !== 1 ||
        output.add(0x28).readU8() !== 1) return null;
    const origin = [0x2c, 0x30, 0x34].map(at => output.add(at).readFloat());
    const q = [0x38, 0x3c, 0x40, 0x44].map(at => output.add(at).readFloat());
    const norm = q.reduce((sum, value) => sum + value * value, 0);
    if (!origin.every(v => Number.isFinite(v) && Math.abs(v) < 10000) ||
        !q.every(Number.isFinite) || norm < .8 || norm > 1.2) return null;
    const [x, y, z, w] = q.map(value => value / Math.sqrt(norm));
    // Impress and CPM use the forward -Z ray before the Axrif conversion.
    return [...origin, -2 * (x * z + w * y), -2 * (y * z - w * x),
        -(1 - 2 * (x * x + y * y))];
}

export function readEyeActionEvent(event) {
    function text(at) {
        const heap = (at.readU8() & 1) !== 0;
        const length = heap ? at.add(8).readU64().toNumber() : at.readU8() >>> 1;
        if (!Number.isInteger(length) || length < 1 || length > 32) return '';
        const data = heap ? at.add(16).readPointer() : at.add(1);
        return data.isNull() ? '' : data.readUtf8String(length);
    }
    if (text(event) !== 'eye') return null;
    const buckets = event.add(0x50).readPointer();
    const count = event.add(0x58).readU64().toNumber();
    if (buckets.isNull() || !Number.isInteger(count) || count < 1 || count > 256) {
        throw new Error('Invalid AZJ2 eye action table');
    }
    for (let i = 0; i < count; i++) {
        const slot = buckets.add(i * 0x80);
        if (slot.add(4).readS16() < 0 || text(slot.add(8)) !== 'aim') continue;
        if (slot.add(0x78).readU32() !== 4) throw new Error('Wrong AZJ2 eye action type');
        return {ray: readEyePose(slot.add(0x20))};
    }
    return {ray: null};
}

export function readEyeActionBatch(batch) {
    const begin = batch.readPointer(), end = batch.add(8).readPointer();
    if (begin.isNull() && end.isNull()) return null;
    if (begin.isNull() || end.compare(begin) < 0 || end.compare(begin.add(64 * 0x80)) > 0) {
        throw new Error('Invalid AZJ2 input batch range');
    }
    const bytes = end.sub(begin).toInt32();
    if (bytes % 0x80 !== 0) throw new Error('Invalid AZJ2 input event stride');
    let eye = null, pinching = false;
    for (let offset = 0; offset < bytes; offset += 0x80) {
        const event = begin.add(offset);
        if (eye === null) eye = readEyeActionEvent(event);
        const hand = readHandActionEvent(event, 0);
        if (hand !== null && hand.sample !== null && hand.sample.pinching) pinching = true;
    }
    return eye === null ? null : {...eye, pinching};
}

export function isPinnedInfo(info) {
    return info !== null && Number(info.xrDesktopMode.value) === 4 &&
        Number(info.userId.value) === 0 && info.baseIntent.value !== null &&
        info.baseIntent.value.hasCategory('boo.puppy.gxr.PINNED_OVERLAY');
}

export function installImmersivePins(Java, factory, permitted, nowMs) {
    const Controller = factory.use('local.gxr.pins.PinnedPanels');
    const controller = Java.retain(Controller.$new());
    const Director = Java.use('com.android.wm.shell.windowdecor.XrCaptionWindowDecorDirector');
    const Decoration = Java.use('com.android.wm.shell.windowdecor.XrCaptionWindowDecoration');
    const BaseDecor = Java.use('com.android.wm.shell.windowdecor.XrWindowDecoration');
    const Overlay = Java.use('com.android.systemui.xr.wm.shell.overlay.OverlayTaskControllerImpl');
    const Runtime = Java.use('com.android.systemui.xr.cpm.XrRuntimeLayer');
    const Transaction = Java.use('android.view.SurfaceControl$Transaction');
    const records = new Map(), hooks = [];
    const signature = 'android.app.ActivityManager$RunningTaskInfo';
    let director = null, nativeHook = null, stopped = false, restored = false, discoveryDone = false;
    let rayTimer = null, latestRay = null, latestPinching = false, cleanupError = null, lastRuntime = '';
    let scrim = null, runtimeFlags = -1;
    let rays = 0, rejected = 0, nativeCalls = 0, eyeEvents = 0, lastError = null, lastSample = -Infinity;
    const noDecor = Director.shouldNotHaveWindowDecor.overload(signature);
    const canShow = Decoration.canShowDecor.overload(signature);
    const appeared = Overlay.handleNewOverlayTask.overload(signature, 'android.view.SurfaceControl',
        'com.android.systemui.xr.spatial.TaskSubspace');
    const changed = Overlay.handleOverlayTaskInfoUpdate.overload(signature);
    const cleanup = Overlay.cleanupTask.overload('int');
    const relayout = BaseDecor.relayout.overload(signature, 'boolean');
    const runtimeVisibility = Runtime.computeXrRuntimeLayerVisibility.overload('boolean', 'boolean', 'boolean', 'boolean');
    const active = () => !stopped && permitted();

    function drop(id) {
        if (scrim !== null) scrim.setAllowed(false);
        const record = records.get(id);
        if (!record) return;
        controller.remove(id);
        if (director !== null) controller.destroyCaption(director, record.info);
        record.info.$dispose();
        record.start.close(); record.start.$dispose();
        record.finish.close(); record.finish.$dispose();
        records.delete(id);
        if (records.size === 0 && nativeHook !== null) {
            nativeHook.detach(); nativeHook = null; latestRay = null;
        }
    }
    function stop() {
        if (stopped) return;
        stopped = true;
        try { if (scrim !== null) scrim.stop(); }
        catch (error) { cleanupError = String(error); }
        if (rayTimer !== null) { clearInterval(rayTimer); rayTimer = null; }
        if (nativeHook !== null) { nativeHook.detach(); nativeHook = null; }
        Java.perform(() => {
            for (const hook of hooks) hook.implementation = null;
            hooks.length = 0;
            controller.shutdown();
            try { for (const id of [...records.keys()]) drop(id); }
            catch (error) { cleanupError = String(error); }
            restored = cleanupError === null;
            if (restored) console.log('GXR_PINS_STOPPED');
        });
    }
    function fail(error) {
        lastError = String(error.stack || error);
        console.log('GXR_PINS_ERROR ' + lastError);
        stop();
    }
    function installEyes() {
        if (nativeHook !== null) return;
        const module = Process.getModuleByName('libspaceflinger_jni_vulkan.so');
        const symbol = '_ZN12spaceflinger12InputManager18handleInputActionsERKNSt3__16vectorIN3imp16InputActionEventENS1_9allocatorIS4_EEEE';
        const address = module.getExportByName(symbol);
        if (!address.equals(module.base.add(0x4d9e5a0)) ||
            address.readU32() !== 0xd503233f || address.add(4).readU32() !== 0xa9ba7bfd) {
            throw new Error('AZJ2 eye input symbol/code mismatch');
        }
        nativeHook = Interceptor.attach(address, {
            onEnter(args) {
                nativeCalls++;
                if (!active() || records.size === 0) return;
                try {
                    const event = readEyeActionBatch(args[1]);
                    if (event === null) return;
                    eyeEvents++;
                    const now = nowMs();
                    if (now - lastSample < 16) return;
                    lastSample = now;
                    latestPinching = event.pinching;
                    const ray = event.ray;
                    latestRay = ray;
                    if (ray === null) { rejected++; return; }
                    rays++;
                } catch (error) { fail(error); }
            },
        });
        if (rayTimer === null) rayTimer = setInterval(() => {
            if (!active() || latestRay === null || records.size === 0) return;
            Java.perform(() => {
                try { controller.setRay(Java.array('float', latestRay), Math.floor(lastSample), latestPinching); }
                catch (error) { fail(error); }
            });
        }, 33);
    }
    try {
        runtimeVisibility.implementation = function (sysui, overlay, immersive, keyguard) {
            runtimeFlags = (sysui ? 1 : 0) | (overlay ? 2 : 0) | (immersive ? 4 : 0) | (keyguard ? 8 : 0);
            if (scrim !== null && runtimeFlags !== 6) scrim.setAllowed(false);
            const result = runtimeVisibility.call(this, sysui, overlay, immersive, keyguard);
            try { controller.setRuntimeState(!!sysui, !!overlay, !!immersive, !!keyguard, !!result); }
            catch (error) { fail(error); }
            return result;
        };
        hooks.push(runtimeVisibility);
        noDecor.implementation = function (info) {
            return active() && isPinnedInfo(info) ? false : noDecor.call(this, info);
        };
        hooks.push(noDecor);
        canShow.implementation = function (info) {
            if (active() && isPinnedInfo(info)) {
                return !!Controller.isTaskVisible(info) && !this.getKeyguardShowing();
            }
            return canShow.call(this, info);
        };
        hooks.push(canShow);
        appeared.implementation = function (info, leash, subspace) {
            if (scrim !== null) scrim.setAllowed(false);
            const result = appeared.call(this, info, leash, subspace);
            if (active()) controller.bindOverlayRepository(this.overlayTaskRepository.value);
            if (!active() || !isPinnedInfo(info)) return result;
            try {
                if (director === null) throw new Error('Caption director is not ready');
                const id = Number(info.taskId.value);
                if (!records.has(id)) {
                    if (records.size >= 8) throw new Error('At most eight pinned windows');
                    const record = {info: Java.retain(info), start: Java.retain(Transaction.$new()),
                        finish: Java.retain(Transaction.$new())};
                    records.set(id, record);
                    director.onTaskOpening(info, leash, record.start, record.finish);
                    record.start.apply(); record.finish.apply();
                    controller.add(id, Java.cast(subspace,
                        Java.use('com.android.systemui.xr.spatial.impl.TaskSubspaceImpl')), info);
                    installEyes();
                    console.log('GXR_PINS_WINDOW ' + id);
                }
            } catch (error) { fail(error); }
            return result;
        };
        hooks.push(appeared);
        changed.implementation = function (info) {
            if (scrim !== null) scrim.setAllowed(false);
            const result = changed.call(this, info);
            if (active()) controller.bindOverlayRepository(this.overlayTaskRepository.value);
            const id = Number(info.taskId.value), record = records.get(id);
            if (active() && record) {
                try {
                    record.info.$dispose();
                    record.info = Java.retain(info);
                    controller.updateInfo(id, info);
                    const decor = director.windowDecorByTaskId.value.get(id);
                    if (decor !== null) relayout.call(Java.cast(decor, BaseDecor), info, false);
                } catch (error) { fail(error); }
            }
            return result;
        };
        hooks.push(changed);
        cleanup.implementation = function (id) {
            try { drop(Number(id)); } catch (error) { fail(error); }
            return cleanup.call(this, id);
        };
        hooks.push(cleanup);
        Java.choose(Director.$className, {
            onMatch(value) {
                if (!stopped && director === null) {
                    director = Java.retain(value);
                    controller.bindCaptionOwner(value);
                }
            },
            onComplete() {
                if (stopped || director === null) {
                    discoveryDone = true;
                    if (!stopped) fail(new Error('Caption director unavailable'));
                    return;
                }
                let found = false;
                Java.choose(Runtime.$className, {
                    onMatch(value) {
                        if (!stopped && !found) { controller.bindRuntime(value); found = true; }
                    },
                    onComplete() {
                        discoveryDone = true;
                        if (!stopped && found) console.log('GXR_PINS_READY - experimental native overlays');
                        else if (!stopped) fail(new Error('Runtime layer unavailable'));
                    },
                });
            },
        });
    } catch (error) { fail(error); }
    return {
        pulse() {
            if (!active()) return;
            controller.pulse(true);
            if (records.size > 0 && scrim === null) scrim = installPinnedScrim(nowMs);
            if (scrim !== null) {
                const allowed = records.size > 0 && runtimeFlags === 6 && controller.isBackdropOverridden();
                scrim.setAllowed(allowed);
                scrim.setInputAllowed(allowed && controller.wantsPinPointer());
            }
            const status = String(controller.getRuntimeStatus());
            if (status !== lastRuntime) {
                lastRuntime = status;
                console.log('GXR_PINS_FOCUS ' + status);
            }
            const error = String(controller.getError());
            if (error) fail(new Error(error));
        },
        stop,
        getRotationTaskIds: () => active() ? [...records.entries()]
            .filter(([, record]) => isPinnedInfo(record.info)).map(([id]) => id) : [],
        canGrab: () => active() && records.size > 0 && runtimeFlags === 6 &&
            controller.isBackdropOverridden() && controller.wantsPinPointer(),
        isRestored: () => stopped && restored && discoveryDone && controller.isRestored(),
        getDiagnostics: () => ({windows: records.size, nativeCalls, eyeEvents, rays, rejected, nativeScrim: scrim !== null,
            nativePinInput: scrim === null ? 0 : scrim.getInputRouting(),
            fullscreenScrim: scrim === null ? null : scrim.getScrimDiagnostics(),
            gaze: String(controller.getStatus()), error: lastError, cleanupError}),
        dispose() {
            if (!this.isRestored()) return;
            if (director !== null) director.$dispose();
            controller.$dispose();
        },
    };
}
