package local.gxr.pins;

import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.graphics.Rect;
import android.content.Context;
import java.io.Closeable;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import local.gxr.rotation.WindowFeatures;

/** Owns marked-panel fading and focus; stock visibility and minimisation stay authoritative. */
public final class PinnedPanels {
    private volatile Handler main = new Handler(Looper.getMainLooper());
    private final AtomicInteger captionCloses = new AtomicInteger();
    private final AtomicInteger resizeCompletions = new AtomicInteger();
    private final Map<Integer, Panel> panels = new LinkedHashMap<>();
    private volatile long heartbeat;
    private volatile boolean stopping;
    private volatile boolean restored;
    private volatile boolean cleanupFailed;
    private volatile String error = "";
    private float[] ray;
    private boolean pinching;
    private long sampledAt = -1;
    private long samples;
    private long hitTests;
    private long hits;
    private volatile String panelStatus = "none";
    private volatile boolean fadeEnabled = true;
    private Object runtimeOwner;
    private Object captionOwner;
    private Object runtimeNode;
    private Object overlayRepository;
    private volatile int runtimeFlags = -1;
    private boolean stockRuntimeVisible = true;
    private volatile boolean transparentBackdrop;
    private volatile boolean inputOverride;
    private volatile boolean pinnedInput;
    private long lastInputOverride;
    private final Runnable runtimeWatchdog = new Runnable() {
        @Override public void run() {
            if (stopping) return;
            updateBackdropSafely();
            if (!stopping) main.postDelayed(this, 250);
        }
    };

    static Object call(Object owner, String name, Class<?>[] types, Object... args) throws Exception {
        Method method = owner.getClass().getMethod(name, types);
        method.setAccessible(true);
        try { return method.invoke(owner, args); }
        catch (InvocationTargetException wrapped) {
            if (wrapped.getCause() instanceof Exception) throw (Exception) wrapped.getCause();
            throw wrapped;
        }
    }
    static Object get(Object owner, String name) throws Exception {
        return call(owner, name, new Class<?>[0]);
    }
    static Object field(Object owner, String name) throws Exception {
        Field member = owner.getClass().getDeclaredField(name);
        member.setAccessible(true);
        return member.get(owner);
    }
    public static boolean isTaskVisible(Object info) throws Exception {
        // Frida gives a same-named method precedence over TaskInfo's boolean fields.
        return info.getClass().getField("isVisible").getBoolean(info) &&
                info.getClass().getField("isVisibleRequested").getBoolean(info);
    }
    public void bindCaptionOwner(Object director) throws Exception {
        main = (Handler) field(director, "mainHandler");
        captionOwner = director;
    }
    private void onOwner(Runnable callback) {
        if (Looper.myLooper() == main.getLooper()) callback.run();
        else if (!main.post(callback)) {
            cleanupFailed = true;
            error = "Caption owner stopped before runtime cleanup";
        }
    }
    public void bindRuntime(Object owner) {
        onOwner(() -> {
            if (stopping) return;
            runtimeOwner = owner;
            main.removeCallbacks(runtimeWatchdog);
            main.post(runtimeWatchdog);
        });
    }
    public void bindOverlayRepository(Object repository) {
        onOwner(() -> {
            if (stopping) return;
            overlayRepository = repository;
            updateBackdropSafely();
        });
    }
    public void setRuntimeState(boolean sysui, boolean overlay, boolean immersive, boolean keyguard, boolean visible) {
        onOwner(() -> {
            if (stopping) return;
            runtimeFlags = (sysui ? 1 : 0) | (overlay ? 2 : 0) | (immersive ? 4 : 0) | (keyguard ? 8 : 0);
            stockRuntimeVisible = visible;
            updateBackdropSafely();
        });
    }
    private void updateBackdropSafely() {
        try { updateBackdrop(); }
        catch (Exception value) { fail(value); }
    }
    @SuppressWarnings("unchecked")
    private void updateBackdrop() throws Exception {
        long now = SystemClock.uptimeMillis();
        boolean live = !stopping && now >= heartbeat && now - heartbeat <= WindowFeatures.SUPERVISOR_LEASE_MS;
        boolean ownedVisible = false;
        boolean ownedInteractive = false;
        for (Panel panel : panels.values()) if (!panel.closed && panel.visible) ownedVisible = true;
        for (Panel panel : panels.values()) if (!panel.closed && panel.visible && panel.inputWanted) ownedInteractive = true;
        boolean foreign = true;
        if (overlayRepository != null && ownedVisible) {
            Set<Integer> requested = (Set<Integer>) field(overlayRepository, "requestedVisibleOverlayTasks");
            foreign = requested.isEmpty() || requested.size() > 64;
            if (!foreign) for (Integer id : requested) if (!panels.containsKey(id)) foreign = true;
        }
        boolean wanted = live && BackdropPolicy.allows(runtimeFlags >= 0, (runtimeFlags & 1) != 0,
                (runtimeFlags & 2) != 0, (runtimeFlags & 4) != 0, (runtimeFlags & 8) != 0,
                ownedVisible, foreign);
        if (!wanted) { restoreRuntime(); return; }
        if (runtimeOwner == null) return;
        if (runtimeNode == null) runtimeNode = field(runtimeOwner, "xrRuntimeLayerNode");
        if (runtimeNode == null) return;
        if (!transparentBackdrop) {
            setNodeScrim(runtimeNode, true);
            transparentBackdrop = true;
        }
        pinnedInput = ownedInteractive;
        if (!inputOverride || now - lastInputOverride >= 1000) {
            setSystemOverlay(false);
            inputOverride = true;
            lastInputOverride = now;
        }
    }
    private static void setSystemOverlay(boolean visible) throws Exception {
        Class.forName("android.graphics.CPM").getMethod("notifySystemOverlayStateChanged", boolean.class)
                .invoke(null, visible);
    }
    private void restoreRuntime() throws Exception {
        Exception failure = null;
        if (transparentBackdrop) {
            try { setNodeScrim(runtimeNode, false); transparentBackdrop = false; }
            catch (Exception value) { failure = value; }
        }
        if (inputOverride) {
            try {
                boolean visible = runtimeOwner == null ? stockRuntimeVisible : Boolean.TRUE.equals(field(runtimeOwner, "isVisible"));
                setSystemOverlay(visible);
                inputOverride = false;
                pinnedInput = false;
            } catch (Exception value) {
                if (failure == null) failure = value;
                else failure.addSuppressed(value);
            }
        }
        if (failure != null) throw failure;
    }
    private static void setNodeScrim(Object node, boolean transparent) throws Exception {
        Class<?> nodeType = Class.forName("android.graphics.CPM$Node");
        Class<?> metadataType = Class.forName("android.graphics.CPM$SysUIMetadata");
        Object metadata = metadataType.getConstructor().newInstance();
        if (transparent) {
            Class<?> vector = Class.forName("android.graphics.CPM$Vec3");
            Object black = vector.getConstructor(float.class, float.class, float.class).newInstance(0f, 0f, 0f);
            Object scrim = Class.forName("android.graphics.CPM$SysUIMetadata$ScrimConfig")
                    .getConstructor(vector, float.class).newInstance(black, 0f);
            metadataType.getField("scrimConfig").set(metadata, scrim);
        }
        Object updates = Class.forName("android.graphics.CPM$NodeUpdates").getConstructor().newInstance();
        try {
            call(updates, "setSysUIMetadata", new Class<?>[] {nodeType, metadataType}, node, metadata);
            get(updates, "apply");
        } finally { get(updates, "close"); }
    }
    public void destroyCaption(Object director, Object info) {
        captionCloses.incrementAndGet();
        Runnable cleanup = () -> {
            try {
                call(director, "destroyWindowDecoration",
                        new Class<?>[] {android.app.ActivityManager.RunningTaskInfo.class}, info);
            } catch (Exception value) {
                cleanupFailed = true;
                error = "Caption cleanup failed: " + value.getMessage();
            } finally { captionCloses.decrementAndGet(); }
        };
        if (Looper.myLooper() == main.getLooper()) cleanup.run();
        else if (!main.post(cleanup)) {
            captionCloses.decrementAndGet();
            cleanupFailed = true;
            error = "Caption owner stopped before cleanup";
        }
    }

    public synchronized void setRay(float[] values, long time, boolean pinched) {
        if (stopping || values == null || values.length != 6) return;
        for (float value : values) if (!Float.isFinite(value) || Math.abs(value) > 10000) return;
        float length = values[3] * values[3] + values[4] * values[4] + values[5] * values[5];
        long now = SystemClock.uptimeMillis();
        if (length < .8f || length > 1.2f || time > now || now - time > 150) return;
        ray = values.clone();
        pinching = pinched;
        sampledAt = time;
        samples++;
    }

    public void add(int taskId, Object subspace, Object info) {
        main.post(() -> {
            if (stopping || panels.containsKey(taskId)) return;
            try {
                if (panels.size() >= 8) throw new IllegalStateException("At most eight pinned panels");
                panels.put(taskId, new Panel(subspace, info));
            } catch (Exception value) { fail(value); }
        });
    }
    public void remove(int taskId) {
        main.post(() -> {
            Panel panel = panels.remove(taskId);
            if (panel != null) panel.restore();
        });
    }
    public void updateInfo(int taskId, Object info) {
        main.post(() -> {
            Panel panel = panels.get(taskId);
            if (panel == null) return;
            try {
                panel.visible = isTaskVisible(info);
                panel.configureMove(info);
            } catch (Exception value) { fail(value); }
        });
    }
    public void pulse(boolean enabled) {
        heartbeat = SystemClock.uptimeMillis();
        fadeEnabled = enabled;
    }
    public String getError() { return error; }
    public synchronized String getStatus() {
        return "attention=window-bounds,samples=" + samples + ",tests=" + hitTests + ",hits=" + hits +
                ",resizePending=" + resizeCompletions.get() +
                ",panel=" + panelStatus +
                "," + getRuntimeStatus();
    }
    public String getRuntimeStatus() {
        return "runtimeFlags=" + runtimeFlags + ",backdrop=" + transparentBackdrop +
                ",inputOverride=" + inputOverride + ",focus=" + (inputOverride ? "vr" : "stock") +
                ",pinPointer=" + (inputOverride && pinnedInput);
    }
    public boolean isBackdropOverridden() { return transparentBackdrop && inputOverride; }
    public boolean wantsPinPointer() { return inputOverride && pinnedInput; }
    public void shutdown() {
        stopping = true;
        main.post(() -> {
            main.removeCallbacks(runtimeWatchdog);
            for (Panel panel : panels.values()) panel.restore();
            panels.clear();
            try { restoreRuntime(); }
            catch (Exception value) { cleanupFailed = true; error = "Runtime restoration failed: " + value.getMessage(); }
            restored = !cleanupFailed;
        });
    }
    public boolean isRestored() {
        return restored && !cleanupFailed && !transparentBackdrop && !inputOverride &&
                captionCloses.get() == 0 && resizeCompletions.get() == 0;
    }

    private void fail(Exception value) {
        Throwable cause = value.getCause() == null ? value : value.getCause();
        error = cause.getClass().getSimpleName() + ": " + cause.getMessage();
        stopping = true;
        main.removeCallbacks(runtimeWatchdog);
        for (Panel panel : panels.values()) panel.restore();
        try { restoreRuntime(); }
        catch (Exception cleanup) { cleanupFailed = true; error += "; runtime restoration failed: " + cleanup.getMessage(); }
    }

    private final class Panel implements Runnable {
        final Object graph;
        final Object node;
        final Class<?> nodeType;
        final Class<?> updatesType;
        final Object transform;
        Object transformListener;
        volatile float[] worldFromNode;
        final Method updateReform;
        final Object[] stockReform = new Object[24];
        final String[] limits = {"MinWidthMeters", "MinHeightMeters", "MaxWidthMeters", "MaxHeightMeters"};
        final Object[] stockLimits = new Object[4];
        PinnedResize resize;
        final FadePolicy fade = new FadePolicy();
        int width, height;
        float widthMeters, heightMeters;
        volatile boolean closed;
        boolean visible = true;
        boolean looking;
        boolean inputWanted = true;
        volatile boolean resizable;

        Panel(Object subspace, Object info) throws Exception {
            graph = get(subspace, "getCpmNodeTree");
            node = get(graph, "getRootNode");
            nodeType = Class.forName("android.graphics.CPM$Node");
            updatesType = Class.forName("android.graphics.CPM$NodeUpdates");
            transform = get(graph, "getNonSpatializedTransformNode");
            Method found = null;
            for (Method method : transform.getClass().getMethods()) {
                if (method.getName().equals("updateReformOptions") && method.getParameterTypes().length == 24) {
                    found = method;
                }
            }
            if (found == null) throw new NoSuchMethodException("AZJ2 movement contract");
            updateReform = found;
            Object state = field(transform, "reformState");
            stockReform[1] = get(state, "getMoveEnabled");
            stockReform[2] = get(state, "getResizeEnabled");
            stockReform[3] = get(state, "getAlphaIsFull");
            Object sizes = field(transform, "reformSizes");
            for (int i = 0; i < limits.length; i++) stockLimits[i] = get(sizes, "get" + limits[i]);
            Object options = field(transform, "reformOptions");
            stockReform[20] = field(options, "boundaryWidthMeters");
            stockReform[21] = field(options, "boundaryCornerRadiusMeters");
            visible = isTaskVisible(info);
            try {
                configureMove(info);
                ClassLoader loader = transform.getClass().getClassLoader();
                Class<?> callbackType = loader.loadClass("kotlin.jvm.functions.Function1");
                Object unit = loader.loadClass("kotlin.Unit").getField("INSTANCE").get(null);
                Object callback = Proxy.newProxyInstance(loader, new Class<?>[] {callbackType},
                        (proxy, method, args) -> {
                    if (method.getName().equals("invoke")) {
                        if (!closed) {
                            Object update = args[0];
                            boolean attached = update.getClass().getField("attached").getBoolean(update);
                            float[] matrix = (float[]) update.getClass().getField("transform").get(update);
                            worldFromNode = attached && matrix != null ? matrix.clone() : null;
                        }
                        return unit;
                    }
                    if (method.getName().equals("hashCode")) return System.identityHashCode(proxy);
                    if (method.getName().equals("equals")) return proxy == args[0];
                    return "PinnedPanelTransform";
                });
                Object factory = field(transform, "transformListenerFactory");
                transformListener = call(factory, "create", new Class<?>[] {nodeType, callbackType},
                        get(graph, "getWindowNode"), callback);
                resize = new PinnedResize(captionOwner, subspace, info, main, resizeCompletions,
                        () -> !closed && !stopping && visible && resizable && SystemClock.uptimeMillis() >= heartbeat &&
                                SystemClock.uptimeMillis() - heartbeat <= WindowFeatures.SUPERVISOR_LEASE_MS,
                        value -> onOwner(() -> fail(value)));
            }
            catch (Exception failure) {
                try { if (transformListener != null) ((Closeable) transformListener).close(); }
                catch (Exception cleanup) { cleanupFailed = true; failure.addSuppressed(cleanup); }
                try { restoreReform(); }
                catch (Exception cleanup) { cleanupFailed = true; failure.addSuppressed(cleanup); }
                throw failure;
            }
            main.post(this);
        }

        void configureMove(Object info) throws Exception {
            Object configuration = info.getClass().getField("configuration").get(info);
            Object window = configuration.getClass().getField("windowConfiguration").get(configuration);
            Rect bounds = (Rect) get(window, "getBounds");
            if (bounds.width() <= 0 || bounds.height() <= 0) throw new IllegalStateException("Invalid panel bounds");
            Class<?> metrics = graph.getClass().getClassLoader().loadClass("com.android.systemui.xr.ui.DisplayMetrics");
            Object density = metrics.getField("INSTANCE").get(null);
            float ppm = ((Number) get(density, "getPixelsPerMeter")).floatValue();
            if (!Float.isFinite(ppm) || ppm <= 0) throw new IllegalStateException("Invalid panel density");
            ClassLoader loader = graph.getClass().getClassLoader();
            Class<?> dp = loader.loadClass("com.android.systemui.xr.ui.unit.Dp");
            int defaultDp = info.getClass().getField("defaultMinSize").getInt(info);
            int defaultPx = ((Number) call(density, "toPx", new Class<?>[] {dp},
                    dp.getConstructor(float.class).newInstance((float) defaultDp))).intValue();
            Object taskSizes = loader.loadClass("com.android.systemui.xr.spatial.impl.TaskSizes").getField("INSTANCE").get(null);
            int minWidth = info.getClass().getField("minWidth").getInt(info);
            int minHeight = info.getClass().getField("minHeight").getInt(info);
            Object minimum = call(taskSizes, "buildMinimumTaskSize",
                    new Class<?>[] {Context.class, Integer.class, Integer.class, Integer.class},
                    field(captionOwner, "context"), minWidth > 0 ? minWidth : null,
                    minHeight > 0 ? minHeight : null, defaultPx > 0 ? defaultPx : null);
            Object maximum = call(taskSizes, "buildMaximumTaskSize", new Class<?>[] {Context.class},
                    field(captionOwner, "context"));
            Object[] args = new Object[24];
            args[1] = true;
            resizable = info.getClass().getField("isResizeable").getBoolean(info);
            args[2] = resizable;
            args[3] = true;
            args[7] = bounds.width() / ppm;
            args[8] = bounds.height() / ppm;
            args[9] = get(minimum, "getX"); args[10] = get(minimum, "getY");
            args[11] = get(maximum, "getX"); args[12] = get(maximum, "getY");
            args[20] = args[21] = call(density, "getDpToMeter", new Class<?>[] {int.class}, 88);
            reform(args);
            width = bounds.width(); height = bounds.height();
            widthMeters = width / ppm; heightMeters = height / ppm;
        }
        void restoreReform() throws Exception {
            Object sizes = field(transform, "reformSizes");
            for (int i = 0; i < limits.length; i++) {
                call(sizes, "set" + limits[i], new Class<?>[] {Float.class}, stockLimits[i]);
            }
            reform(stockReform);
        }
        void reform(Object[] values) throws Exception {
            Object updates = updatesType.getConstructor().newInstance();
            try {
                Object[] args = values.clone();
                args[0] = updates;
                updateReform.invoke(transform, args);
                get(updates, "apply");
            } finally { get(updates, "close"); }
        }

        @Override public void run() {
            if (closed) return;
            try {
                long now = SystemClock.uptimeMillis();
                float[] current;
                long time;
                boolean held;
                synchronized (PinnedPanels.this) { current = ray; time = sampledAt; held = pinching; }
                boolean allowed = !stopping && visible && now >= heartbeat && now - heartbeat <= WindowFeatures.SUPERVISOR_LEASE_MS;
                float[] local = PanelRay.toLocal(worldFromNode, current);
                boolean fresh = allowed && local != null && now >= time && now - time <= 150;
                if (fresh && fadeEnabled) {
                    hitTests++;
                    looking = PanelRay.hitsPanel(local, widthMeters, heightMeters);
                    if (looking) hits++;
                }
                float alpha = fade.update(now, fresh, looking, allowed && fadeEnabled, held);
                inputWanted = allowed && fade.wantsInput();
                setAlpha(alpha);
                panelStatus = "transform=" + (worldFromNode != null) + ":fresh=" + fresh +
                        ":looking=" + looking + ":pinching=" + held + ":alpha=" + alpha +
                        ":size=" + width + "x" + height + ":resizable=" + resizable;
                main.postDelayed(this, 33);
            } catch (Exception value) { fail(value); }
        }

        void setAlpha(float opacity) throws Exception {
            if (Boolean.TRUE.equals(field(graph, "released"))) return;
            Object state = get(graph, "getAlpha");
            float stock = ((Number) get(state, "getValue")).floatValue();
            float value = Math.max(0, Math.min(1, stock)) * opacity;
            Object updates = updatesType.getConstructor().newInstance();
            try {
                call(updates, "setAlpha", new Class<?>[] {nodeType, float.class}, node, value);
                get(updates, "apply");
            } finally { get(updates, "close"); }
        }
        void restore() {
            closed = true;
            main.removeCallbacks(this);
            try {
                try {
                    try { if (resize != null) resize.close(); }
                    finally {
                        if (transformListener != null) {
                            ((Closeable) transformListener).close();
                            transformListener = null;
                        }
                    }
                } finally {
                    try {
                        if (!Boolean.TRUE.equals(field(graph, "released"))) restoreReform();
                    } finally { setAlpha(1); }
                }
            }
            catch (Exception value) {
                cleanupFailed = true;
                error = "Opacity restoration failed: " + value.getMessage();
            }
        }
    }
}
