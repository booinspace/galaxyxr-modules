// Column-major composition preserves Samsung's own boundary size and offset.
export function boundaryTransform(window, visual) {
    for (const matrix of [window, visual]) {
        if (matrix.length !== 16 || !matrix.every(v => Number.isFinite(v) && Math.abs(v) <= 1e6) ||
            [3, 7, 11].some(i => Math.abs(matrix[i]) > 1e-5) || Math.abs(matrix[15] - 1) > 1e-5) {
            throw new Error('Invalid boundary transform');
        }
    }
    return Array.from({length: 16}, (_, i) => {
        const row = i % 4, column = Math.floor(i / 4);
        return [0, 1, 2, 3].reduce((sum, k) => sum + window[k * 4 + row] * visual[column * 4 + k], 0);
    });
}

function uniformScaleSquared(matrix) {
    const columns = [0, 4, 8].map(i => matrix.slice(i, i + 3));
    const dot = (a, b) => a.reduce((sum, v, i) => sum + v * b[i], 0);
    const scale = dot(columns[0], columns[0]);
    return scale < 1e-10 || columns.some(c => Math.abs(dot(c, c) - scale) > scale * 1e-4) ||
        [[0, 1], [0, 2], [1, 2]].some(([a, b]) => Math.abs(dot(columns[a], columns[b])) > scale * 1e-4)
        ? null : scale;
}

export function resizeHitInParent(window, baseline, point) {
    const aligned = boundaryTransform(window, baseline), scale = uniformScaleSquared(window);
    if (scale === null || point.length !== 3 || !point.every(v => Number.isFinite(v) && Math.abs(v) <= 1e6)) {
        throw new Error('Invalid resize hit transform');
    }
    const delta = point.map((v, i) => v - window[12 + i]);
    // Stock corner tests subtract the aligned visual position but ignore its rotation.
    return [0, 1, 2].map(i => delta.reduce((sum, v, j) => sum + window[i * 4 + j] * v, 0) / scale
        + aligned[12 + i] - baseline[12 + i]);
}

/** Experimental boundary alignment; leaves stock drag events and the app node untouched. */
export function installBoundaryAlignment(allowed, onError) {
    const renderer = Process.getModuleByName('libsysui_jni_soong_vulkan.so');
    const impress = Process.getModuleByName('libImpress-jni-vulkan.so');
    function address(module, symbol, offset) {
        const value = module.getExportByName(symbol);
        if (!value.equals(module.base.add(offset))) throw new Error('AZJ2 boundary symbol mismatch: ' + symbol);
        return value;
    }
    function native(symbol, offset, result, args = ['pointer']) {
        return new NativeFunction(address(impress, symbol, offset), result, args);
    }
    const getNode = native('_ZNK3imp9Component7GetNodeEv', 0x12e24f8, ['uint64', 'pointer']);
    const valid = native('_ZNK3imp10NodeHandle7IsValidEv', 0x12f1964, 'bool');
    const parent = native('_ZNK3imp4Node9GetParentEv', 0x12ec70c, ['uint64', 'pointer']);
    const getName = native('_ZNK3imp4Node7GetNameEv', 0x12ebe2c, ['pointer', 'ulong']);
    const getChildren = native('_ZNK3imp4Node11GetChildrenEv', 0x12ec75c, ['pointer', 'pointer', 'pointer']);
    const getTrs = native('_ZNK3imp4Node11GetLocalTrsEv', 0x12ecc64, 'pointer');
    const setTrs = new NativeFunction(address(impress,
        '_ZN3imp4Node11SetLocalTrsERKN8filament4math7details6TMat44IfEE', 0x12ec510), 'void', ['pointer', 'pointer']);
    const localFromWorld = native('_ZNK3imp4Node19LocalFromWorldPointERKN8filament4math7details5TVec3IfEE',
        0x12ed824, ['float', 'float', 'float'], ['pointer', 'pointer']);
    const worldFromLocal = native('_ZNK3imp4Node19WorldFromLocalPointERKN8filament4math7details5TVec3IfEE',
        0x12ee4bc, ['float', 'float', 'float'], ['pointer', 'pointer']);
    const release = new NativeFunction(Module.getGlobalExportByName('_ZdlPv'), 'void', ['pointer']);
    const identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
    const records = new Map(), depths = new Map(), hooks = [];
    let stopping = false, applied = 0;
    const diagnostics = {renderer: renderer.name, highlightUpdates: 0, placeholderUpdates: 0, resizes: 0,
        resizeHitTests: 0, resizeCornerHits: 0,
        rejected: {}, last: 'waiting-for-callback', parents: [], path: []};
    function skip(reason) {
        diagnostics.last = reason;
        diagnostics.rejected[reason] = (diagnostics.rejected[reason] || 0) + 1;
    }
    function handle(parts) {
        const result = Memory.alloc(16);
        result.writeU64(parts[0]);
        result.add(8).writePointer(parts[1]);
        return result;
    }
    function same(parts, node) {
        // NodeHandle's entity is 32 bits; the upper half of the ABI word is padding.
        return parseInt(parts[0].toString(16).slice(-8), 16) === node.readU32()
            && parts[1].equals(node.add(8).readPointer());
    }
    function name(node) {
        const [text, length] = getName(node);
        return length > 0 && length <= 80 && !text.isNull() ? text.readUtf8String(length) : '';
    }
    function matrix(node) {
        const data = getTrs(node);
        return Array.from({length: 16}, (_, i) => data.add(i * 4).readFloat());
    }
    function write(node, values) {
        const data = Memory.alloc(64);
        values.forEach((value, i) => data.add(i * 4).writeFloat(value));
        setTrs(node, data);
    }
    function children(node) {
        const [begin, end] = getChildren(node);
        try {
            const bytes = Number(end.sub(begin).toString()), count = bytes / 16;
            if (!Number.isSafeInteger(bytes) || !Number.isInteger(count) || count < 0 || count > 64) {
                throw new Error('Invalid boundary child count');
            }
            return Array.from({length: count}, (_, i) => {
                const copy = Memory.alloc(16);
                Memory.copy(copy, begin.add(i * 16), 16);
                return copy;
            });
        } finally { if (!begin.isNull()) release(begin); }
    }
    function pathToWindow(node, target, depth = 0, budget = {remaining: 64}) {
        if (!valid(node) || --budget.remaining < 0) throw new Error('Invalid boundary scene graph');
        const label = name(node);
        if (diagnostics.path.length < 8) diagnostics.path.push(label);
        if (label === target) return [node];
        if (depth === 4) return null;
        for (const child of children(node)) {
            const found = pathToWindow(child, target, depth + 1, budget);
            if (found !== null) return [node, ...found];
        }
        return null;
    }
    function restore(component, discard = false) {
        const key = component.toString(), record = records.get(key);
        if (record === undefined) return;
        if (record.baseline !== null && valid(record.node)) write(record.node, record.baseline);
        record.baseline = null;
        record.window = null;
        if (discard) records.delete(key);
    }
    function apply(component) {
        if (stopping) return;
        const key = component.toString();
        let record = records.get(key);
        if (record === undefined) {
            const node = handle(getNode(component));
            if (!valid(node)) { skip('node-invalid'); return; }
            const owner = handle(parent(node));
            if (!valid(owner)) { skip('owner-invalid'); return; }
            const label = name(owner);
            if (diagnostics.parents.length < 8 && !diagnostics.parents.includes(label)) diagnostics.parents.push(label);
            const match = /^space-transform-task-(\d+)$/.exec(label);
            if (match === null) { skip('parent-name'); return; }
            if (!allowed(Number(match[1]))) { skip('task-not-ready'); return; }
            diagnostics.path = [];
            const path = pathToWindow(owner, 'window-task-' + match[1]);
            if (path === null) { skip('window-missing'); return; }
            if (records.size >= 64) throw new Error('Too many boundary visuals');
            record = {node, path, task: Number(match[1]), baseline: null};
            records.set(key, record);
        }
        if (!allowed(record.task) || record.path.some(node => !valid(node)) || !valid(record.node)) {
            records.delete(key);
            skip('node-or-task-lost');
            return;
        }
        // A stock transition can replace or reparent nodes between frames.
        if (!same(parent(record.node), record.path[0]) || record.path.slice(1).some((node, i) =>
            !same(parent(node), record.path[i]))) { records.delete(key); skip('path-changed'); return; }
        let window = identity;
        for (const node of record.path.slice(1)) window = boundaryTransform(window, matrix(node));
        if (window.every((value, i) => Math.abs(value - identity[i]) < 1e-6)) { skip('identity'); return; }
        // SetLocalTrs decomposes TRS; a skewed or collapsed transition is not representable.
        if (uniformScaleSquared(window) === null) {
            skip('nonuniform-or-skewed'); return;
        }
        const baseline = matrix(record.node);
        const aligned = boundaryTransform(window, baseline);
        record.baseline = baseline;
        record.window = window;
        write(record.node, aligned);
        diagnostics.last = 'aligned';
        if (++applied === 1) console.log('GXR_BOUNDARY_ALIGNED task=' + record.task);
    }
    function guarded(operation) {
        try { operation(); }
        catch (error) { stopping = true; onError(error); }
    }
    const visuals = [
        ['15HighlightVisual', 0x4d0ba98, 0x4d0c194, 0x4c97c60, 0x4c97d30],
        ['23ResizePlaceholderVisual', 0x4d1622c, 0x4d16074, 0x4c99828, 0x4c998f8],
    ];
    // All symbols are resolved before attaching; full library hashes are pinned by control.sh.
    const targets = visuals.map(([type, update, resize, active, cleanup]) => [
        [`_ZN2ix6moohan5sysui${type}6UpdateERKN3imp9FrameTimeE`, update],
        [`_ZN2ix6moohan5sysui${type}21UpdateSizeAndPositionERKN8filament4math7details5TVec2IfEERKNS5_5TVec3IfEE`, resize],
        [`_ZN3imp13ComponentPoolIN2ix6moohan5sysui${type}EE12NotifyActiveEPNS_9ComponentEb`, active],
        [`_ZN3imp13ComponentPoolIN2ix6moohan5sysui${type}EE7CleanupERNS_9ComponentE`, cleanup],
    ].map(([symbol, offset]) => address(renderer, symbol, offset)));
    const renderState = address(renderer,
        '_ZN2ix6moohan5sysui16ReformController21GetCurrentRenderStateERKNSt3__18optionalIN3imp13GenericRayHitIfEEEE',
        0x4d13470);
    try {
        for (const [index, [update, resize, active, cleanup]] of targets.entries()) {
            for (const target of [update, resize]) hooks.push(Interceptor.attach(target, {
                onEnter(args) {
                    diagnostics[target.equals(update) ? (index === 0 ? 'highlightUpdates' : 'placeholderUpdates') : 'resizes']++;
                    this.component = args[0];
                    const key = this.component.toString(), depth = depths.get(key) || 0;
                    depths.set(key, depth + 1);
                    if (depth === 0) guarded(() => restore(this.component));
                },
                onLeave() {
                    const key = this.component.toString(), depth = depths.get(key) - 1;
                    if (depth > 0) { depths.set(key, depth); return; }
                    depths.delete(key);
                    guarded(() => apply(this.component));
                },
            }));
            hooks.push(Interceptor.attach(active, {onEnter(args) {
                if ((args[2].toInt32() & 1) === 0) guarded(() => restore(args[1], true));
            }}));
            hooks.push(Interceptor.attach(cleanup, {onEnter(args) { guarded(() => restore(args[1], true)); }}));
        }
        hooks.push(Interceptor.attach(renderState, {
            onEnter(args) {
                guarded(() => {
                    const controller = args[0], hit = args[1];
                    if (stopping || hit.isNull() || hit.add(0x60).readU8() === 0 ||
                        (controller.add(0x20).readU32() & 2) === 0) return;
                    const highlight = controller.add(0x98).readPointer();
                    const record = records.get(highlight.toString());
                    if (record === undefined || record.baseline === null || !allowed(record.task) ||
                        !valid(record.node) || record.path.some(node => !valid(node)) ||
                        !same(getNode(controller), record.path[0]) || !same(parent(record.node), record.path[0])) return;
                    const point = resizeHitInParent(record.window, record.baseline,
                        localFromWorld(record.path[0], hit.add(0x14)));
                    const local = Memory.alloc(12);
                    point.forEach((v, i) => local.add(i * 4).writeFloat(v));
                    const world = worldFromLocal(record.path[0], local);
                    if (!world.every(v => Number.isFinite(v) && Math.abs(v) <= 1e6)) throw new Error('Invalid resize world point');
                    // Only this classifier reads the copy; the original ray and resize events are unchanged.
                    const copy = Memory.alloc(0x68);
                    Memory.copy(copy, hit, 0x61);
                    world.forEach((v, i) => copy.add(0x14 + i * 4).writeFloat(v));
                    this.hitCopy = copy;
                    args[1] = copy;
                    diagnostics.resizeHitTests++;
                });
            },
            onLeave(result) {
                if (this.hitCopy !== undefined && result.toInt32() >= 2 && result.toInt32() <= 5) {
                    diagnostics.resizeCornerHits++;
                }
            },
        }));
    } catch (error) { for (const hook of hooks) hook.detach(); throw error; }
    return {
        stop() { stopping = true; },
        getDiagnostics() {
            return {...diagnostics, rejected: {...diagnostics.rejected}, parents: diagnostics.parents.slice(),
                path: diagnostics.path.slice(), aligned: applied, cached: records.size};
        },
        isRestored() { return stopping && depths.size === 0 && [...records.values()].every(r => r.baseline === null); },
        dispose() {
            if (!this.isRestored()) throw new Error('Boundary cleanup still pending');
            for (const hook of hooks) hook.detach();
            records.clear();
        },
    };
}
