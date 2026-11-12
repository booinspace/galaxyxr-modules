package local.gxr.rotation;

import android.app.ActivityManager.RunningTaskInfo;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.view.View;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.lang.ref.WeakReference;

/** Java owns callbacks and rollback, including after the injector disappears. */
public final class RotationController {
    private final List<Session> sessions = new ArrayList<>();
    private final List<Pending> pending = new ArrayList<>();
    private final List<Window> windows = new ArrayList<>();
    private volatile long heartbeat = SystemClock.uptimeMillis();
    private volatile boolean stopping;
    private volatile boolean homeSpace = true;
    private volatile boolean enabled = true;
    private volatile boolean grabEnabled;
    private volatile String error = "";
    private volatile String grabStatus = "idle";

    static Object field(Object object, String name) throws Exception {
        for (Class<?> type = object.getClass(); type != null; type = type.getSuperclass()) {
            try {
                Field member = type.getDeclaredField(name);
                member.setAccessible(true);
                return member.get(object);
            } catch (NoSuchFieldException ignored) { /* Private fields can belong to a superclass. */ }
        }
        throw new NoSuchFieldException(name);
    }

    static Object call(Object object, String name, Class<?>[] types, Object... args) throws Exception {
        for (Class<?> type = object.getClass(); type != null; type = type.getSuperclass()) {
            try {
                Method method = type.getDeclaredMethod(name, types);
                method.setAccessible(true);
                try { return method.invoke(object, args); }
                catch (InvocationTargetException wrapped) {
                    Throwable cause = wrapped.getCause();
                    if (cause instanceof Exception) throw (Exception) cause;
                    if (cause instanceof Error) throw (Error) cause;
                    throw wrapped;
                }
            } catch (NoSuchMethodException ignored) { /* Try the inherited contract. */ }
        }
        throw new NoSuchMethodException(name);
    }

    static Object call(Object object, String name) throws Exception {
        return call(object, name, new Class<?>[0]);
    }

    static View root(Object menu) throws Exception {
        Object pill = field(menu, "moreActionsPill");
        return pill == null ? null : (View) call(pill, "getView");
    }

    static boolean is2d(Object task) throws Exception {
        Object state = call(task, "is2DRenderingEnabled");
        return Boolean.TRUE.equals(call(state, "getValue"));
    }

    public void pulse() { heartbeat = SystemClock.uptimeMillis(); }
    /** The shared window runtime supplies Home Space eligibility with its pulse. */
    public void pulse(boolean home) { homeSpace = home; pulse(); }
    public String getError() { return error; }

    public synchronized void setEnabled(boolean value) {
        enabled = value;
        if (!value) for (Session session : sessions) session.handler.post(session::restore);
    }

    public synchronized void setGrabEnabled(boolean value) {
        grabEnabled = value;
        if (!value) cancelGrabs();
    }

    public synchronized void cancelGrabs() {
        for (Session session : sessions) session.handler.post(() -> session.grabId = -1);
    }

    private static boolean excluded(String pkg) {
        return "android".equals(pkg) || "com.android.systemui".equals(pkg)
                || "com.samsung.android.app.xr.home".equals(pkg) || "me.weishu.kernelsu".equals(pkg);
    }

    private static final class Window {
        final int taskId;
        final Object repository;
        final WeakReference<View> view;
        Window(int taskId, Object repository, View root) {
            this.taskId = taskId;
            this.repository = repository;
            view = new WeakReference<>(root);
        }
    }

    /** The existing caption hook supplies the real view owner for grab callbacks. */
    public synchronized void bindWindow(Object decor, View root) throws Exception {
        if (stopping) return;
        RunningTaskInfo info = (RunningTaskInfo) field(decor, "mTaskInfo");
        if (info.topActivity == null || excluded(info.topActivity.getPackageName())) return;
        windows.removeIf(old -> old.view.get() == null || old.taskId == info.taskId);
        if (windows.size() >= 32) throw new IllegalStateException("Too many caption bindings");
        windows.add(new Window(info.taskId, field(decor, "taskSubspaceRepository"), root));
    }

    /** Boundary eligibility follows live rotation bindings, even without a Curve menu. */
    public synchronized int[] getBoundTaskIds() throws Exception {
        if (stopping || !enabled || !homeSpace || SystemClock.uptimeMillis() - heartbeat > 5000) return new int[0];
        int[] ids = new int[windows.size()];
        int count = 0;
        for (Window window : windows) {
            View view = window.view.get();
            if (view == null || !view.isAttachedToWindow()) continue;
            Object task = call(window.repository, "getTaskSubspace", new Class<?>[] {int.class}, window.taskId);
            if (task != null && is2d(task)) ids[count++] = window.taskId;
        }
        return Arrays.copyOf(ids, count);
    }

    /** Reform callbacks can lack a looper; post rotation on the caption's owning view. */
    public synchronized void onGrab(Object transform, int id, int state, float[] hand,
            float[] parent, long sampledAt) throws Exception {
        if (!enabled || !grabEnabled || stopping || !homeSpace) { grabStatus = "inactive"; return; }
        grabStatus = "not-bound";
        for (Window window : windows) {
            View view = window.view.get();
            if (view == null || !view.isAttachedToWindow()) { grabStatus = "caption-detached"; continue; }
            Object repository = window.repository;
            int taskId = window.taskId;
            Object task = call(repository, "getTaskSubspace", new Class<?>[] {int.class}, taskId);
            if (task == null) continue;
            if (!transform.equals(call(task, "getNonSpatializedTransformNode")) || !is2d(task)) {
                grabStatus = "target-mismatch";
                continue;
            }
            Object node = call(task, "getCpmWindowNode");
            grabStatus = "queued";
            if (!view.post(() -> {
                try {
                    if (!enabled || !grabEnabled || stopping || !homeSpace
                            || !view.isAttachedToWindow()
                            || SystemClock.uptimeMillis() - heartbeat > 5000) return;
                    long age = SystemClock.uptimeMillis() - sampledAt;
                    if (age < 0 || age > 150) {
                        grabStatus = "stale";
                        synchronized (RotationController.this) {
                            for (Session old : sessions) if (old.taskId == taskId) old.grabId = -1;
                        }
                        return;
                    }
                    Object current = call(repository, "getTaskSubspace", new Class<?>[] {int.class}, taskId);
                    if (current == null || !is2d(current) || !node.equals(call(current, "getCpmWindowNode"))) return;
                    try { call(node, "getNativeHandle"); }
                    catch (IllegalStateException closed) { return; }
                    Session session = session(repository, node, taskId);
                    if (state == 0 || state == 3) {
                        if (session.grabId == id) session.grabId = -1;
                        grabStatus = "released";
                        return;
                    }
                    if (state == 1) {
                        session.grabId = id;
                        session.handStart = RotationMath.normalize(hand);
                        session.parentStart = RotationMath.normalize(parent);
                        session.localStart = session.orientation.clone();
                        grabStatus = "started";
                    } else if (state == 2 && session.grabId == id) {
                        if (session.currentTask() == null) { session.grabId = -1; return; }
                        session.orientation = RotationMath.grabbed(session.handStart, hand, session.parentStart,
                                parent, session.localStart);
                        int[] angles = RotationMath.degrees(session.orientation);
                        System.arraycopy(angles, 0, session.angles, 0, 3);
                        session.update();
                        grabStatus = "applied";
                        for (RotationMenu menu : session.menus) menu.root.post(menu::refresh);
                    }
                } catch (Exception failure) { fail(failure); }
            })) throw new IllegalStateException("Caption rejected its grab callback");
            return;
        }
    }

    private synchronized Session session(Object repository, Object node, int taskId) throws Exception {
        sessions.removeIf(old -> old.finished);
        for (Session candidate : sessions) {
            if (candidate.taskId == taskId && candidate.node.equals(node) && !candidate.closing) return candidate;
        }
        if (sessions.size() >= 16) throw new IllegalStateException("Too many rotation sessions");
        Session created = new Session(repository, node, taskId);
        sessions.add(created);
        return created;
    }

    void fail(Exception failure) {
        error = failure.toString();
        shutdown();
    }

    public synchronized String getStatus() {
        int active = 0;
        for (Session session : sessions) if (!session.finished) active++;
        return "sessions=" + active + ",pending=" + pending.size()
                + ",bindings=" + windows.size() + ",grab=" + grabStatus;
    }

    public synchronized boolean isRestored() {
        if (!stopping || !pending.isEmpty()) return false;
        for (Session session : sessions) if (!session.finished) return false;
        return true;
    }

    public synchronized void shutdown() {
        stopping = true;
        windows.clear();
        for (Pending item : pending) item.view.removeCallbacks(item);
        pending.clear();
        for (Session session : sessions) session.handler.post(session::restore);
    }

    /** bindMenu runs before first layout; View.post selects the view's owning looper. */
    public void onMenu(Object menu) throws Exception {
        View view = root(menu);
        if (view == null) return;
        Pending item = new Pending(menu, view);
        synchronized (this) {
            if (stopping || !homeSpace || SystemClock.uptimeMillis() - heartbeat > 5000) return;
            if (pending.size() >= 16) throw new IllegalStateException("Too many pending menus");
            pending.add(item);
        }
        if (!view.post(item)) {
            synchronized (this) { pending.remove(item); }
            throw new IllegalStateException("Menu rejected its layout callback");
        }
    }

    private final class Pending implements Runnable {
        final Object menu;
        final View view;
        Pending(Object menu, View view) { this.menu = menu; this.view = view; }
        @Override public void run() {
            synchronized (RotationController.this) { pending.remove(this); }
            try { attachMenu(menu, view, false); }
            catch (Exception failure) { fail(failure); }
        }
    }

    /** Called on the menu owner; Curvature owns the shared surface dimensions. */
    public RotationMenu attachMenu(Object menu, View view) throws Exception {
        return attachMenu(menu, view, true);
    }

    private RotationMenu attachMenu(Object menu, View view, boolean sharedHost) throws Exception {
        if (stopping || !enabled || !homeSpace || SystemClock.uptimeMillis() - heartbeat > 5000
                || root(menu) != view || !view.isAttachedToWindow()) return null;
        Object decor = field(menu, "parentDecor");
        RunningTaskInfo info = (RunningTaskInfo) field(decor, "mTaskInfo");
        if (info.topActivity == null) return null;
        String pkg = info.topActivity.getPackageName();
        if (excluded(pkg)) return null;
        // A restored window can predate the delayed caption hook; its menu can bind the real caption.
        View caption = (View) field(field(decor, "relayoutResult"), "mRootView");
        if (caption != null) bindWindow(decor, caption);
        Object repository = field(decor, "taskSubspaceRepository");
        Object task = call(repository, "getTaskSubspace", new Class<?>[] {int.class}, info.taskId);
        if (task == null || !is2d(task)) return null;
        Object node = call(task, "getCpmWindowNode");
        if (node == null) return null;
        call(node, "getNativeHandle");
        Session session = session(repository, node, info.taskId);
        return session.addMenu(menu, view, sharedHost);
    }

    final class Session {
        final Object repository;
        final Object node;
        final int taskId;
        final Handler handler;
        final List<RotationMenu> menus = new ArrayList<>();
        final int[] angles = {0, 0, 0};
        float[] orientation = {1, 0, 0, 0};
        int grabId = -1;
        float[] handStart;
        float[] parentStart;
        float[] localStart;
        final Class<?> updatesType;
        final Method setOrientation;
        final Method apply;
        final Method close;
        volatile boolean finished;
        boolean closing;
        private final Runnable watchdog = new Runnable() {
            @Override public void run() {
                if (finished) return;
                try {
                    Object task = currentTask();
                    if (closing || stopping || !enabled || !homeSpace || SystemClock.uptimeMillis() - heartbeat > 5000
                            || task == null || !is2d(task)) {
                        restore();
                        return;
                    }
                    menus.removeIf(menu -> menu.closed);
                    handler.postDelayed(this, 500);
                } catch (Exception failure) {
                    error = failure.toString();
                    restore();
                }
            }
        };

        Session(Object repository, Object node, int taskId) throws Exception {
            Looper looper = Looper.myLooper();
            if (looper == null) throw new IllegalStateException("Rotation needs a view looper");
            this.repository = repository;
            this.taskId = taskId;
            handler = new Handler(looper);
            updatesType = Class.forName("android.graphics.CPM$NodeUpdates");
            setOrientation = updatesType.getMethod("setOrientation", Class.forName("android.graphics.CPM$Node"),
                    float.class, float.class, float.class, float.class);
            apply = updatesType.getMethod("apply");
            close = updatesType.getMethod("close");
            this.node = call(node, "deepCopy");
            try {
                call(this.node, "getNativeHandle");
                if (this.node == node || !node.equals(this.node)) {
                    throw new IllegalStateException("Rotation must own a reference to the same node");
                }
                if (!handler.postDelayed(watchdog, 500)) throw new IllegalStateException("Rotation looper stopped");
            } catch (Exception failure) {
                if (this.node != node) {
                    try { call(this.node, "close"); }
                    catch (Exception cleanup) { failure.addSuppressed(cleanup); }
                }
                throw failure;
            }
        }

        Object currentTask() throws Exception {
            Object task = call(repository, "getTaskSubspace", new Class<?>[] {int.class}, taskId);
            if (task == null) return null;
            Object current = call(task, "getCpmWindowNode");
            if (current == null) return null;
            try {
                call(current, "getNativeHandle");
                if (!node.equals(current)) return null;
            } catch (IllegalStateException closed) { return null; }
            return task;
        }

        RotationMenu addMenu(Object menu, View view, boolean sharedHost) throws Exception {
            if (closing || finished) return null;
            if (Looper.myLooper() != handler.getLooper()) throw new IllegalStateException("Menu looper changed");
            for (RotationMenu old : menus) if (!old.closed && old.root == view) return old;
            RotationMenu attachment = new RotationMenu(RotationController.this, this, menu, view, sharedHost);
            menus.add(attachment);
            return attachment;
        }

        void set(int axis, int degrees) throws Exception {
            if (axis < 0 || axis > 2 || degrees < -180 || degrees > 180) {
                throw new IllegalArgumentException("Invalid rotation control value");
            }
            Object task = currentTask();
            if (closing || stopping || !enabled || finished || !homeSpace || task == null || !is2d(task)
                    || SystemClock.uptimeMillis() - heartbeat > 5000) {
                throw new IllegalStateException("Window is no longer eligible");
            }
            angles[axis] = degrees;
            grabId = -1;
            orientation = RotationMath.orientation(angles[0], angles[1], angles[2]);
            update();
            Log.i("GXRRotation", "task=" + taskId + " pitch=" + angles[0]
                    + " yaw=" + angles[1] + " roll=" + angles[2]);
        }

        void reset() throws Exception {
            if (currentTask() == null) throw new IllegalStateException("Task node was released");
            angles[0] = angles[1] = angles[2] = 0;
            grabId = -1;
            orientation = new float[] {1, 0, 0, 0};
            update();
        }

        private void update() throws Exception {
            float[] q = orientation;
            Object updates = updatesType.getConstructor().newInstance();
            try {
                setOrientation.invoke(updates, node, q[0], q[1], q[2], q[3]);
                apply.invoke(updates);
            } finally { close.invoke(updates); }
        }

        void restore() {
            if (finished) return;
            closing = true;
            handler.removeCallbacks(watchdog);
            try {
                // The owned same-node reference remains valid after stock closes its wrapper.
                angles[0] = angles[1] = angles[2] = 0;
                grabId = -1;
                orientation = new float[] {1, 0, 0, 0};
                update();
                for (RotationMenu menu : menus) menu.close(true);
                menus.clear();
                call(node, "close");
                finished = true;
            } catch (Exception failure) {
                error = failure.toString();
                handler.postDelayed(watchdog, 500);
            }
        }
    }
}
