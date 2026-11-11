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
import java.util.List;

/** Java owns callbacks and rollback, including after the injector disappears. */
public final class RotationController {
    private final List<Session> sessions = new ArrayList<>();
    private final List<Pending> pending = new ArrayList<>();
    private volatile long heartbeat = SystemClock.uptimeMillis();
    private volatile boolean stopping;
    private volatile boolean homeSpace = true;
    private volatile String error = "";

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

    void fail(Exception failure) {
        error = failure.toString();
        shutdown();
    }

    public synchronized String getStatus() {
        int active = 0;
        for (Session session : sessions) if (!session.finished) active++;
        return "sessions=" + active + ",pending=" + pending.size();
    }

    public synchronized boolean isRestored() {
        if (!stopping || !pending.isEmpty()) return false;
        for (Session session : sessions) if (!session.finished) return false;
        return true;
    }

    public synchronized void shutdown() {
        stopping = true;
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
        if (stopping || !homeSpace || SystemClock.uptimeMillis() - heartbeat > 5000
                || root(menu) != view || !view.isAttachedToWindow()) return null;
        Object decor = field(menu, "parentDecor");
        RunningTaskInfo info = (RunningTaskInfo) field(decor, "mTaskInfo");
        if (info.topActivity == null) return null;
        String pkg = info.topActivity.getPackageName();
        if ("android".equals(pkg) || "com.android.systemui".equals(pkg)
                || "com.samsung.android.app.xr.home".equals(pkg)
                || "me.weishu.kernelsu".equals(pkg)) return null;
        Object repository = field(decor, "taskSubspaceRepository");
        Object task = call(repository, "getTaskSubspace", new Class<?>[] {int.class}, info.taskId);
        if (task == null || !is2d(task)) return null;
        Object node = call(task, "getCpmWindowNode");
        if (node == null) return null;
        call(node, "getNativeHandle");
        Session session = null;
        synchronized (RotationController.this) {
            if (stopping) return null;
            sessions.removeIf(old -> old.finished);
            for (Session candidate : sessions) {
                if (candidate.taskId == info.taskId && candidate.node.equals(node)) session = candidate;
            }
            if (session == null) {
                if (sessions.size() >= 16) throw new IllegalStateException("Too many rotation sessions");
                session = new Session(repository, node, info.taskId);
                sessions.add(session);
            }
        }
        return session.addMenu(menu, view, sharedHost);
    }

    final class Session {
        final Object repository;
        final Object node;
        final int taskId;
        final Handler handler;
        final List<RotationMenu> menus = new ArrayList<>();
        final int[] angles = {0, 0, 0};
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
                    if (closing || stopping || !homeSpace || SystemClock.uptimeMillis() - heartbeat > 5000
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
            if (closing || stopping || finished || !homeSpace || task == null || !is2d(task)
                    || SystemClock.uptimeMillis() - heartbeat > 5000) {
                throw new IllegalStateException("Window is no longer eligible");
            }
            angles[axis] = degrees;
            update();
            Log.i("GXRRotation", "task=" + taskId + " pitch=" + angles[0]
                    + " yaw=" + angles[1] + " roll=" + angles[2]);
        }

        void reset() throws Exception {
            if (currentTask() == null) throw new IllegalStateException("Task node was released");
            angles[0] = angles[1] = angles[2] = 0;
            update();
        }

        private void update() throws Exception {
            float[] q = RotationMath.orientation(angles[0], angles[1], angles[2]);
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
