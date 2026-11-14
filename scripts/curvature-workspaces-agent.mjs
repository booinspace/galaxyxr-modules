/** Only the root-owned Window Controls FIFO can submit this bounded optional helper. */
export class WorkspaceUpload {
    constructor() { this.reset(); }
    reset() { this.transfer = null; }
    accept(line, now) {
        if (typeof line !== 'string' || line.length > 3500 || !Number.isFinite(now)) throw new Error('Invalid workspace frame');
        let match = /^ws-begin ([0-9a-f]{32}) ([0-9a-f]{64}) ([1-9][0-9]{0,5})$/.exec(line);
        if (match) {
            const size = Number(match[3]);
            if (size > 512 * 1024) throw new Error('Workspace helper exceeds limit');
            this.transfer = {token: match[1], sha: match[2], size, data: '', started: now}; return null;
        }
        match = /^ws-(part|end) ([0-9a-f]{32})(?: ([A-Za-z0-9+/=]{1,2800}))?$/.exec(line);
        if (!match || (match[1] === 'part') !== (match[3] !== undefined)) throw new Error('Invalid workspace upload');
        const transfer = this.transfer;
        if (!transfer || transfer.token !== match[2] || now < transfer.started || now - transfer.started > 15000) {
            this.reset(); throw new Error('Workspace transfer expired');
        }
        if (match[1] === 'part') {
            transfer.data += match[3];
            if (transfer.data.length > Math.ceil(transfer.size / 3) * 4) { this.reset(); throw new Error('Workspace transfer overflow'); }
            return null;
        }
        this.reset();
        if (transfer.data.length !== Math.ceil(transfer.size / 3) * 4) throw new Error('Incomplete workspace transfer');
        return transfer;
    }
}

export function hasWorkspaceDexHeader(bytes) {
    return bytes.length >= 4 && (bytes[0] & 255) === 100 && (bytes[1] & 255) === 101 &&
        (bytes[2] & 255) === 120 && (bytes[3] & 255) === 10;
}

export function installWorkspaces(Java, factory, repository, rotation, ensureCurvature, permitted, nowMs, log) {
    const upload = new WorkspaceUpload();
    let controller = null, bridge = null, token = '', lastPing = -Infinity;
    let stopped = false, loading = false, error = '', hooks = [], curvature = null;
    const retired = [];
    function release() {
        for (const method of hooks) method.implementation = null;
        hooks = [];
        if (controller !== null) { controller.stop(); retired.push(controller); controller = null; }
        if (bridge !== null) { bridge.close(); bridge.$dispose(); bridge = null; }
        curvature = null; token = '';
    }
    function unavailable(reason) {
        error = String(reason.stack || reason); log('WORKSPACES_ERROR', {error}); release();
    }
    function reap() {
        for (let i = retired.length - 1; i >= 0; i--) if (retired[i].isStopped()) { retired[i].$dispose(); retired.splice(i, 1); }
    }
    function load(transfer) {
        if (loading || stopped || !permitted()) return;
        reap();
        if (controller !== null && token === transfer.token) return;
        if (controller !== null || retired.length) throw new Error('Previous workspace runtime is still stopping; retry Action shortly');
        loading = true;
        const started = nowMs();
        const phase = stage => log('WORKSPACES_LOAD', {stage, elapsedMs: Math.round(nowMs() - started), bytes: transfer.size});
        phase('decode');
        try {
            const bytes = Java.use('android.util.Base64').decode(transfer.data, 2);
            if (bytes.length !== transfer.size) throw new Error('Workspace DEX size mismatch');
            const digest = Java.use('java.security.MessageDigest').getInstance('SHA-256').digest(bytes);
            const sha = Array.from(digest, value => (value & 255).toString(16).padStart(2, '0')).join('');
            if (sha !== transfer.sha || !hasWorkspaceDexHeader(bytes)) throw new Error('Workspace DEX checksum mismatch');
            phase('validated');
            const loader = Java.use('dalvik.system.InMemoryDexClassLoader').$new(Java.use('java.nio.ByteBuffer').wrap(bytes), factory.loader);
            const child = Java.ClassFactory.get(loader);
            const app = Java.use('android.app.ActivityThread').currentApplication();
            if (app === null) throw new Error('SystemUI application is unavailable');
            phase('loader-created');
            bridge = Java.retain(factory.use('local.gxr.workspacehost.WorkspaceWindowHost').$new(app.getApplicationContext(), repository, rotation));
            const Controller = child.use('local.gxr.workspaces.WorkspaceController');
            phase('classes-ready');
            controller = Java.retain(Controller.$new(app.getApplicationContext(), bridge, transfer.token));
            phase('controller-created');
            token = transfer.token; lastPing = nowMs(); error = '';
            const Overview = Java.use('com.android.systemui.xr.overview.ui.OverviewXrElement');
            for (const method of [Overview.onCreate.overload('android.os.Bundle'), Overview.onResume.overload()]) {
                method.implementation = function (...args) {
                    const result = method.call(this, ...args);
                    try { if (controller !== null && permitted()) controller.attachOverview(this); }
                    catch (failure) { unavailable(failure); }
                    return result;
                };
                hooks.push(method);
            }
            log('WORKSPACES_READY', {nativeRecents: true, standalone: true, loadMs: Math.round(nowMs() - started)});
        } catch (failure) { unavailable(failure); }
        finally { loading = false; }
    }
    return {
        accept(command) {
            if (!command.startsWith('ws-')) return false;
            if (stopped) return true;
            try {
                let match = /^ws-(ping|off) ([0-9a-f]{32})$/.exec(command);
                if (match) {
                    if (match[2] === token) {
                        if (match[1] === 'ping') lastPing = nowMs();
                        else Java.perform(release);
                    }
                    return true;
                }
                if (command === 'ws-stop') { upload.reset(); Java.perform(release); return true; }
                const transfer = upload.accept(command, nowMs());
                if (transfer !== null) Java.perform(() => load(transfer));
            } catch (failure) { error = String(failure); upload.reset(); log('WORKSPACES_UPLOAD_ERROR', {error}); }
            return true;
        },
        pulse(tasks) {
            reap();
            if (controller === null) return;
            try {
                if (stopped || !permitted() || nowMs() - lastPing > 5000) { release(); return; }
                bridge.pulse(); controller.pulse();
                const rows = Array.from(tasks, ([id, entry]) => [id, Number(entry.session.getValue())]);
                bridge.updateCurvatures(Java.array('int', rows.map(row => row[0])), Java.array('float', rows.map(row => row[1])));
                if (curvature === null) {
                    const line = String(bridge.poll());
                    if (line) {
                        const match = /^([1-9][0-9]*) ([1-9][0-9]*) (0(?:\.[0-9]+)?|1(?:\.0+)?)$/.exec(line);
                        if (!match) throw new Error('Invalid native workspace curvature request');
                        curvature = {id: Number(match[1]), task: Number(match[2]), value: Number(match[3]), until: nowMs() + 2000};
                    }
                }
                if (curvature !== null) {
                    const request = curvature;
                    if (!bridge.requestLive(request.id)) { curvature = null; return; }
                    try {
                        if (ensureCurvature(request.task, request.value, bridge)) { bridge.complete(request.id, ''); curvature = null; }
                        else if (nowMs() > request.until) throw new Error('Window renderer is not ready; saved layout was preserved');
                    } catch (failure) { bridge.complete(request.id, String(failure)); curvature = null; }
                }
            } catch (failure) { unavailable(failure); }
        },
        stop() { stopped = true; upload.reset(); release(); },
        isStopped() { reap(); return !loading && controller === null && retired.length === 0; },
        status() { return {running: controller !== null, state: controller === null ? '' : String(controller.status()), error}; },
    };
}
