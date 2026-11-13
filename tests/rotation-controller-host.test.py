"""Exercise the real rotation controller against small Android/CPM test doubles."""

import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "android/os/Looper.java": """package android.os;
public final class Looper {
    private static final Looper OWNER = new Looper();
    public static Looper myLooper() { return OWNER; }
}
""",
    "android/os/SystemClock.java": """package android.os;
public final class SystemClock {
    public static long now;
    public static long uptimeMillis() { return now; }
}
""",
    "android/os/Handler.java": """package android.os;
import java.util.ArrayList;
public final class Handler {
    private static final ArrayList<Item> QUEUE = new ArrayList<>();
    private final Looper owner;
    private static final class Item {
        final Runnable callback; final long time;
        Item(Runnable callback, long time) { this.callback = callback; this.time = time; }
    }
    public Handler(Looper owner) { this.owner = owner; }
    public Looper getLooper() { return owner; }
    public boolean post(Runnable callback) { return postDelayed(callback, 0); }
    public boolean postDelayed(Runnable callback, long delay) {
        QUEUE.add(new Item(callback, SystemClock.now + delay)); return true;
    }
    public void removeCallbacks(Runnable callback) { QUEUE.removeIf(item -> item.callback == callback); }
    public static void runDue() {
        for (int limit = 0; limit < 1000; limit++) {
            Item next = null;
            for (Item item : QUEUE) if (item.time <= SystemClock.now) { next = item; break; }
            if (next == null) return;
            QUEUE.remove(next); next.callback.run();
        }
        throw new AssertionError("Unbounded callback loop");
    }
}
""",
    "android/view/View.java": """package android.view;
import android.os.Handler;
import android.os.Looper;
public class View {
    private final Handler handler = new Handler(Looper.myLooper());
    public boolean attached = true;
    public int posts;
    public boolean isAttachedToWindow() { return attached; }
    public boolean post(Runnable callback) { posts++; return handler.post(callback); }
    public void removeCallbacks(Runnable callback) { handler.removeCallbacks(callback); }
}
""",
    "android/util/Log.java": """package android.util;
public final class Log { public static int i(String tag, String value) { return 0; } }
""",
    "android/content/ComponentName.java": """package android.content;
public final class ComponentName { public String getPackageName() { return "example.video"; } }
""",
    "android/app/ActivityManager.java": """package android.app;
import android.content.ComponentName;
public final class ActivityManager {
    public static final class RunningTaskInfo {
        public int taskId = 42;
        public ComponentName topActivity = new ComponentName();
    }
}
""",
    "com/android/wm/shell/windowdecor/XrCaptionWindowDecoration.java": """package com.android.wm.shell.windowdecor;
public final class XrCaptionWindowDecoration extends local.gxr.rotation.RotationControllerTest.Decor { }
""",
    "android/graphics/CPM.java": """package android.graphics;
public final class CPM {
    public static final class Node {
        public static Node copy;
        public static boolean wrongCopy;
        private static long nextHandle;
        public final long handle;
        private final long nodeId;
        public int closes;
        public Node(long nodeId) { this.nodeId = nodeId; this.handle = ++nextHandle; }
        public long getNativeHandle() {
            if (closes != 0) throw new IllegalStateException("Stock wrapper is closed");
            return handle;
        }
        public Node deepCopy() { copy = new Node(nodeId + (wrongCopy ? 1 : 0)); return copy; }
        @Override public boolean equals(Object value) {
            return value instanceof Node && nodeId == ((Node) value).nodeId;
        }
        @Override public int hashCode() { return Long.valueOf(nodeId).hashCode(); }
        public void close() { if (++closes != 1) throw new IllegalStateException("Double close"); }
    }
    public static final class NodeUpdates {
        public static float[] last;
        public NodeUpdates setOrientation(Node node, float w, float x, float y, float z) {
            node.getNativeHandle(); last = new float[] {w, x, y, z}; return this;
        }
        public void apply() { }
        public void close() { }
    }
}
""",
    "local/gxr/rotation/RotationMenu.java": """package local.gxr.rotation;
import android.view.View;
public final class RotationMenu implements AutoCloseable {
    public static boolean failNextClose;
    public static RotationMenu last;
    final View root;
    final RotationController.Session session;
    final boolean sharedHost;
    boolean closed;
    RotationMenu(RotationController controller, RotationController.Session session,
            Object menu, View root, boolean sharedHost) {
        this.root = root; this.session = session; this.sharedHost = sharedHost; last = this;
    }
    void close(boolean dismiss) throws Exception {
        if (failNextClose) { failNextClose = false; throw new Exception("Menu cleanup failed"); }
        closed = true;
    }
    @Override public void close() throws Exception { close(false); }
    void refresh() { }
}
""",
    "local/gxr/rotation/RotationControllerTest.java": """package local.gxr.rotation;
import android.app.ActivityManager.RunningTaskInfo;
import android.graphics.CPM;
import android.os.Handler;
import android.os.SystemClock;
import android.view.View;
public final class RotationControllerTest {
    public static final class State { public Boolean getValue() { return true; } }
    public static final class Task {
        final Object transform = new Object();
        CPM.Node node = new CPM.Node(42);
        public Object getNonSpatializedTransformNode() { return transform; }
        public CPM.Node getCpmWindowNode() { return node; }
        public State is2DRenderingEnabled() { return new State(); }
    }
    public static final class Repository {
        final Task task = new Task();
        public Task getTaskSubspace(int id) { return id == 42 ? task : null; }
    }
    public static class Decor {
        final RunningTaskInfo mTaskInfo = new RunningTaskInfo();
        final Repository taskSubspaceRepository = new Repository();
        final RelayoutResult relayoutResult = new RelayoutResult();
    }
    public static final class RelayoutResult { final View mRootView = new View(); }
    public static final class Decorations {
        final java.util.List<Object> values = new java.util.ArrayList<>();
        public int size() { return values.size(); }
        public Object valueAt(int index) { return values.get(index); }
    }
    public static final class Director {
        final Handler mainHandler = new Handler(android.os.Looper.myLooper());
        final Decorations windowDecorByTaskId = new Decorations();
    }
    public static final class Pill {
        final View view = new View();
        public View getView() { return view; }
    }
    public static final class Menu { final Pill moreActionsPill = new Pill(); final Decor parentDecor = new Decor(); }
    private static final class Fixture {
        final RotationController controller = new RotationController();
        final Menu menu = new Menu();
        RotationMenu attach() throws Exception { return controller.attachMenu(menu, menu.moreActionsPill.view); }
        void stop() { controller.shutdown(); Handler.runDue(); }
    }
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    private static void identity() {
        float[] q = CPM.NodeUpdates.last;
        check(q[0] == 1 && q[1] == 0 && q[2] == 0 && q[3] == 0);
    }
    public static void main(String[] args) throws Exception {
        Fixture owned = new Fixture();
        RotationMenu controls = owned.attach();
        check(controls.sharedHost && owned.attach() == controls);
        CPM.Node copy = CPM.Node.copy;
        check(copy.handle != owned.menu.parentDecor.taskSubspaceRepository.task.node.handle);
        check(copy.equals(owned.menu.parentDecor.taskSubspaceRepository.task.node));
        controls.session.set(2, 90);
        owned.menu.parentDecor.taskSubspaceRepository.task.node.close();
        owned.controller.shutdown();
        check(!owned.controller.isRestored());
        Handler.runDue(); identity();
        check(owned.controller.isRestored() && copy.closes == 1 && controls.closed);
        owned.stop(); check(copy.closes == 1);

        Fixture rewrapped = new Fixture();
        controls = rewrapped.attach();
        CPM.Node previous = rewrapped.menu.parentDecor.taskSubspaceRepository.task.node;
        rewrapped.menu.parentDecor.taskSubspaceRepository.task.node = previous.deepCopy();
        check(rewrapped.attach() == controls);
        previous.close(); controls.session.set(2, 45);
        rewrapped.stop(); identity(); check(rewrapped.controller.isRestored());

        Fixture retry = new Fixture();
        retry.attach(); copy = CPM.Node.copy; RotationMenu.failNextClose = true;
        retry.stop(); check(!retry.controller.isRestored() && copy.closes == 0);
        SystemClock.now += 500; Handler.runDue(); identity();
        check(retry.controller.isRestored() && copy.closes == 1);

        Fixture home = new Fixture();
        controls = home.attach(); home.controller.pulse(false);
        check(home.attach() == null);
        SystemClock.now += 500; Handler.runDue();
        check(controls.closed); identity(); home.stop(); check(home.controller.isRestored());

        Fixture expiry = new Fixture();
        controls = expiry.attach(); SystemClock.now += 5001; Handler.runDue();
        check(controls.closed); identity(); expiry.stop(); check(expiry.controller.isRestored());

        Fixture closed = new Fixture();
        controls = closed.attach(); copy = CPM.Node.copy;
        closed.menu.parentDecor.taskSubspaceRepository.task.node.close();
        SystemClock.now += 500; Handler.runDue();
        check(controls.closed && copy.closes == 1 && closed.controller.getError().isEmpty());
        closed.stop(); check(closed.controller.isRestored());

        Fixture isolated = new Fixture();
        isolated.controller.onMenu(isolated.menu); Handler.runDue();
        check(!RotationMenu.last.sharedHost); isolated.stop();

        Fixture wrong = new Fixture(); CPM.Node.wrongCopy = true;
        try { wrong.attach(); throw new AssertionError("Wrong node accepted"); }
        catch (IllegalStateException expected) { check(CPM.Node.copy.closes == 1); }
        finally { CPM.Node.wrongCopy = false; }
        wrong.stop();
        Fixture bound = new Fixture();
        View caption = bound.menu.parentDecor.relayoutResult.mRootView;
        check(bound.controller.getBoundTaskIds().length == 0);
        bound.controller.bindWindow(bound.menu.parentDecor, caption);
        check(bound.controller.getBoundTaskIds().length == 1 && bound.controller.getBoundTaskIds()[0] == 42);
        caption.attached = false;
        check(bound.controller.getBoundTaskIds().length == 0);
        caption.attached = true;
        bound.controller.pulse(false);
        check(bound.controller.getBoundTaskIds().length == 0);
        bound.controller.pulse(true);
        check(bound.controller.getBoundTaskIds().length == 1);
        bound.controller.setEnabled(false);
        check(bound.controller.getBoundTaskIds().length == 1); // Distance does not depend on rotation being enabled.
        bound.stop();
        check(bound.controller.getBoundTaskIds().length == 0);
        Fixture grab = new Fixture();
        grab.controller.setGrabEnabled(true);
        Object transform = grab.menu.parentDecor.taskSubspaceRepository.task.transform;
        float[] initial = RotationMath.orientation(0, 0, 0);
        float[] roll = RotationMath.orientation(0, 0, 90);
        grab.controller.onGrab(transform, 7, 1, initial, initial, SystemClock.now);
        Handler.runDue();
        check(grab.controller.getStatus().contains("grab=not-bound"));
        controls = grab.attach();
        check(grab.controller.getStatus().contains("bindings=1"));
        grab.menu.moreActionsPill.view.attached = false;
        grab.controller.onGrab(transform, 7, 1, initial, initial, SystemClock.now);
        Handler.runDue();
        grab.controller.onGrab(transform, 7, 2, roll, initial, SystemClock.now);
        Handler.runDue();
        check(Math.abs(CPM.NodeUpdates.last[3] - .70710677f) < .00001f);
        check(grab.menu.parentDecor.relayoutResult.mRootView.posts > 0);
        check(grab.controller.getStatus().contains("grab=applied"));
        grab.menu.moreActionsPill.view.attached = true;
        controls = grab.attach();
        check(controls.session.angles[2] == 90);
        grab.controller.onGrab(transform, 7, 3, roll, initial, SystemClock.now);
        Handler.runDue();
        grab.controller.onGrab(transform, 7, 2, initial, initial, SystemClock.now);
        Handler.runDue();
        check(controls.session.angles[2] == 90);
        grab.controller.setGrabEnabled(false); Handler.runDue();
        controls.session.set(2, 20);
        check(controls.session.angles[2] == 20);
        grab.controller.onGrab(transform, 8, 1, initial, initial, SystemClock.now);
        grab.controller.onGrab(transform, 8, 2, roll, initial, SystemClock.now);
        Handler.runDue();
        check(controls.session.angles[2] == 20);
        grab.controller.setEnabled(false); Handler.runDue(); identity();
        check(grab.attach() == null);
        grab.controller.setEnabled(true);
        check(grab.attach() != null);
        grab.stop(); check(grab.controller.isRestored());
        Fixture pin = new Fixture();
        pin.controller.pulse(false, new int[] {43});
        pin.controller.bindWindow(pin.menu.parentDecor, pin.menu.parentDecor.relayoutResult.mRootView);
        check(pin.attach() == null && pin.controller.getBoundTaskIds().length == 0);
        pin.controller.setGrabEnabled(true);
        transform = pin.menu.parentDecor.taskSubspaceRepository.task.transform;
        pin.controller.onGrab(transform, 9, 1, initial, initial, SystemClock.now);
        Handler.runDue();
        check(pin.controller.getStatus().contains("sessions=0"));
        int[] pins = {42};
        pin.controller.pulse(false, pins); pins[0] = 43;
        check(pin.controller.getBoundTaskIds().length == 1);
        controls = pin.attach(); check(controls != null);
        for (int axis = 0; axis < 3; axis++) controls.session.set(axis, 30);
        check(controls.session.angles[0] == 30 && controls.session.angles[1] == 30 && controls.session.angles[2] == 30);
        controls.session.reset();
        pin.controller.onGrab(transform, 9, 1, initial, initial, SystemClock.now);
        Handler.runDue();
        float[] tilted = RotationMath.orientation(25, -40, 60);
        pin.controller.onGrab(transform, 9, 2, tilted, initial, SystemClock.now);
        Handler.runDue();
        check(pin.controller.getStatus().contains("grab=applied"));
        for (int i = 0; i < 4; i++) check(Math.abs(CPM.NodeUpdates.last[i] - tilted[i]) < .00001f);
        pin.controller.onGrab(transform, 9, 3, tilted, initial, SystemClock.now);
        Handler.runDue();
        pin.controller.pulse(false, new int[] {42});
        SystemClock.now += 500; Handler.runDue();
        check(!controls.closed);
        for (int i = 0; i < 4; i++) check(Math.abs(CPM.NodeUpdates.last[i] - tilted[i]) < .00001f);
        pin.controller.onGrab(transform, 10, 1, initial, initial, SystemClock.now);
        pin.controller.pulse(false, new int[0]);
        Handler.runDue(); check(!pin.controller.getStatus().contains("grab=started"));
        SystemClock.now += 500; Handler.runDue(); identity(); check(controls.closed);
        pin.stop(); check(pin.controller.isRestored());
        Fixture invalidPin = new Fixture();
        for (int[] invalid : new int[][] {null, {0}, {-1}, new int[9]}) {
            try { invalidPin.controller.pulse(false, invalid); throw new AssertionError("Invalid pins accepted"); }
            catch (IllegalArgumentException expected) { }
        }
        invalidPin.stop();
        Fixture restoredCaption = new Fixture();
        Director director = new Director();
        Decor captionDecor = new com.android.wm.shell.windowdecor.XrCaptionWindowDecoration();
        director.windowDecorByTaskId.values.add(new Object()); // Non-caption system decorations stay excluded.
        director.windowDecorByTaskId.values.add(captionDecor);
        restoredCaption.controller.bindExistingWindows(director);
        check(restoredCaption.controller.getBoundTaskIds().length == 0);
        Handler.runDue();
        check(restoredCaption.controller.getBoundTaskIds().length == 1);
        restoredCaption.controller.setGrabEnabled(true);
        transform = captionDecor.taskSubspaceRepository.task.transform;
        restoredCaption.controller.onGrab(transform, 17, 1, initial, initial, SystemClock.now);
        Handler.runDue();
        restoredCaption.controller.onGrab(transform, 17, 2, roll, initial, SystemClock.now);
        Handler.runDue();
        check(restoredCaption.controller.getStatus().contains("grab=applied"));
        check(Math.abs(CPM.NodeUpdates.last[3] - .70710677f) < .00001f);
        restoredCaption.stop(); identity();
        Fixture cancelledScan = new Fixture();
        cancelledScan.controller.bindExistingWindows(director);
        cancelledScan.stop();
        check(cancelledScan.controller.getBoundTaskIds().length == 0 && cancelledScan.controller.isRestored());
        System.out.println("PASS: node ownership, rollback, Home/pin isolation, three-axis pin grabs and heartbeat expiry");
        System.out.println("PASS: restored captions bind without opening a menu; shutdown cancels queued discovery");
    }
}
""",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", required=True, type=Path)
    parser.add_argument("--ecj", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gxr-rotation-host-") as temporary:
        work = Path(temporary)
        paths = []
        for name, text in SOURCES.items():
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            paths.append(path)
        production = ROOT / "modules/window-rotation/android/local/gxr/rotation"
        paths.extend(production / name for name in ("RotationController.java", "RotationMath.java", "WindowFeatures.java"))
        output = work / "classes"
        subprocess.run([str(args.java), "-jar", str(args.ecj), "-source", "1.8", "-target", "1.8",
                        "-proc:none", "-d", str(output), *(str(path) for path in paths)], check=True)
        subprocess.run([str(args.java), "-cp", str(output), "local.gxr.rotation.RotationControllerTest"], check=True)


if __name__ == "__main__":
    main()
