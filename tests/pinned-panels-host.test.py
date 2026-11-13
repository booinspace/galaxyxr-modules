"""Run the real pinned-panel helpers with Android doubles and installed Kotlin/coroutines."""
import argparse
from pathlib import Path
import runpy
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ROTATION = runpy.run_path(str(ROOT / "tests/rotation-controller-host.test.py"))["SOURCES"]
SOURCES = {name: ROTATION[name] for name in ("android/os/Looper.java", "android/os/SystemClock.java",
                                           "android/os/Handler.java", "android/graphics/CPM.java")}
SOURCES["android/os/Looper.java"] = SOURCES["android/os/Looper.java"].replace(
    "public static Looper myLooper()", "public static Looper getMainLooper() { return OWNER; }\n    public static Looper myLooper()")
SOURCES["android/graphics/CPM.java"] = SOURCES["android/graphics/CPM.java"].replace(
    "public void apply()", "public void setAlpha(Node node, float value) { }\n        public void apply()")
SOURCES.update({
    "android/app/ActivityManager.java": "package android.app; public class ActivityManager { public static class RunningTaskInfo { } }",
    "android/content/Context.java": "package android.content; public class Context { }",
    "android/window/WindowContainerToken.java": "package android.window; public class WindowContainerToken { }",
    "android/util/Size.java": """package android.util;
public final class Size {
    private final int width, height;
    public Size(int width, int height) { this.width = width; this.height = height; }
    public int getWidth() { return width; } public int getHeight() { return height; }
}
""",
    "android/graphics/Rect.java": """package android.graphics;
public final class Rect {
    public int left, top, right, bottom;
    public Rect(int left, int top, int right, int bottom) {
        this.left = left; this.top = top; this.right = right; this.bottom = bottom;
    }
    public Rect(Rect other) { this(other.left, other.top, other.right, other.bottom); }
    public int width() { return right - left; } public int height() { return bottom - top; }
}
""",
    "com/android/systemui/xr/ui/unit/Dp.java": """package com.android.systemui.xr.ui.unit;
public final class Dp { public final float value; public Dp(float value) { this.value = value; } }
""",
    "com/android/systemui/xr/ui/DisplayMetrics.java": """package com.android.systemui.xr.ui;
import com.android.systemui.xr.ui.unit.Dp;
public final class DisplayMetrics {
    public static final DisplayMetrics INSTANCE = new DisplayMetrics();
    public float getPixelsPerMeter() { return 1000; }
    public int toPx(Dp dp) { return (int) (dp.value * 2); }
    public float getDpToMeter(int dp) { return dp * .002f; }
}
""",
    "com/android/systemui/xr/spatial/impl/TaskSizes.java": """package com.android.systemui.xr.spatial.impl;
import android.content.Context;
public final class TaskSizes {
    public static final TaskSizes INSTANCE = new TaskSizes();
    public static final class Size {
        final float x, y; Size(float x, float y) { this.x = x; this.y = y; }
        public float getX() { return x; } public float getY() { return y; }
    }
    public Size buildMinimumTaskSize(Context context, Integer width, Integer height, Integer fallback) {
        return new Size((width == null || fallback == null ? 64 : Math.max(width, fallback)) / 1000f,
                (height == null || fallback == null ? 32 : Math.max(height, fallback)) / 1000f);
    }
    public Size buildMaximumTaskSize(Context context) { return new Size(3, 2); }
}
""",
    "com/android/systemui/xr/spatial/TaskSubspace.java": """package com.android.systemui.xr.spatial;
import android.util.Size;
import kotlinx.coroutines.channels.Channel;
public interface TaskSubspace {
    public static final class PanelBoundsChangeEvent {
        private final int width, height; private final Channel<Size> complete;
        public PanelBoundsChangeEvent(int width, int height, Channel<Size> complete) {
            this.width = width; this.height = height; this.complete = complete;
        }
        public int getNewWidthPx() { return width; } public int getNewHeightPx() { return height; }
        public Channel<Size> getOnComplete() { return complete; }
    }
}
""",
    "local/gxr/pins/PinnedPanelsTest.java": """package local.gxr.pins;
import android.content.Context;
import android.graphics.CPM;
import android.graphics.Rect;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Size;
import android.window.WindowContainerToken;
import java.io.Closeable;
import java.util.ArrayList;
import java.util.concurrent.atomic.AtomicInteger;
import kotlin.Unit;
import kotlin.coroutines.EmptyCoroutineContext;
import kotlin.jvm.functions.Function1;
import kotlinx.coroutines.*;
import kotlinx.coroutines.channels.*;
import kotlinx.coroutines.flow.*;
import com.android.systemui.xr.spatial.TaskSubspace.PanelBoundsChangeEvent;
public final class PinnedPanelsTest {
    public static final class State { public Float getValue() { return 1f; } }
    public static final class ReformState {
        public Boolean getMoveEnabled() { return false; }
        public Boolean getResizeEnabled() { return false; }
        public Boolean getAlphaIsFull() { return false; }
    }
    public static final class Limits {
        Float minWidth, minHeight = .12f, maxWidth = 2f, maxHeight;
        public Float getMinWidthMeters() { return minWidth; } public void setMinWidthMeters(Float v) { minWidth = v; }
        public Float getMinHeightMeters() { return minHeight; } public void setMinHeightMeters(Float v) { minHeight = v; }
        public Float getMaxWidthMeters() { return maxWidth; } public void setMaxWidthMeters(Float v) { maxWidth = v; }
        public Float getMaxHeightMeters() { return maxHeight; } public void setMaxHeightMeters(Float v) { maxHeight = v; }
    }
    public static final class Options { float boundaryWidthMeters = .04f, boundaryCornerRadiusMeters = .03f; }
    public static final class ListenerFactory {
        int closes;
        public Closeable create(CPM.Node node, Function1<Object, Unit> callback) { return () -> closes++; }
    }
    public static final class Transform {
        final ReformState reformState = new ReformState(); final Limits reformSizes = new Limits();
        final Options reformOptions = new Options(); final ListenerFactory transformListenerFactory = new ListenerFactory();
        Object[] last;
        public void updateReformOptions(CPM.NodeUpdates u, Boolean move, Boolean resize, Boolean alpha,
                Boolean splash, Boolean core, Boolean attached, Float width, Float height,
                Float minW, Float minH, Float maxW, Float maxH, Float resizeW, Float resizeH,
                Float aspect, Object constraints, Object adjustment, Integer orientation, Boolean ongoing,
                Float boundary, Float corner, Boolean follow, Boolean mini) {
            last = new Object[] {move, resize, alpha, width, height, minW, minH, maxW, maxH, boundary, corner};
            if (minW != null) reformSizes.minWidth = minW; if (minH != null) reformSizes.minHeight = minH;
            if (maxW != null) reformSizes.maxWidth = maxW; if (maxH != null) reformSizes.maxHeight = maxH;
            if (boundary != null) reformOptions.boundaryWidthMeters = boundary;
            if (corner != null) reformOptions.boundaryCornerRadiusMeters = corner;
        }
    }
    public static final class Graph {
        boolean released; final CPM.Node node = new CPM.Node(42); final Transform transform = new Transform();
        public CPM.Node getRootNode() { return node; } public CPM.Node getWindowNode() { return node; }
        public Transform getNonSpatializedTransformNode() { return transform; }
        public State getAlpha() { return new State(); }
    }
    public static final class Subspace {
        final Graph graph = new Graph();
        final MutableSharedFlow<Object> events = SharedFlowKt.MutableSharedFlow(0, 8, BufferOverflow.DROP_OLDEST);
        public Graph getCpmNodeTree() { return graph; } public Flow<Object> getEvents() { return events; }
    }
    public static final class WindowConfig {
        Rect bounds = new Rect(0, 0, 800, 600); public Rect getBounds() { return bounds; }
    }
    public static final class Config { public final WindowConfig windowConfiguration = new WindowConfig(); }
    public static final class Info {
        public boolean isVisible = true, isVisibleRequested = true, isResizeable = true;
        public int minWidth = 300, minHeight = 200, defaultMinSize = 100;
        public final Config configuration = new Config(); public final WindowContainerToken token = new WindowContainerToken();
    }
    public static final class Operations {
        int calls; boolean automatic = true; boolean throwsOnResize; Function1<? super Rect, Unit> callback;
        public void resizeTask(WindowContainerToken token, Size size, Function1<? super Rect, Unit> complete) {
            calls++; callback = complete;
            if (throwsOnResize) throw new IllegalStateException("fixture resize failed");
            if (automatic) complete.invoke(new Rect(0, 0, size.getWidth(), size.getHeight()));
        }
    }
    public static final class Director {
        final Handler mainHandler = new Handler(Looper.myLooper()); final Context context = new Context();
        final Operations taskOperations = new Operations();
        final CoroutineScope coroutineScope = CoroutineScopeKt.CoroutineScope(Dispatchers.getUnconfined());
    }
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    private static Size receive(Channel<Size> channel) throws Exception {
        return BuildersKt.runBlocking(EmptyCoroutineContext.INSTANCE, (scope, continuation) -> channel.receive(continuation));
    }
    private static Channel<Size> emit(Subspace subspace, int width, int height, int capacity) {
        Channel<Size> channel = ChannelKt.Channel(capacity, BufferOverflow.SUSPEND, null);
        check(subspace.events.tryEmit(new PanelBoundsChangeEvent(width, height, channel))); return channel;
    }
    public static void main(String[] args) throws Exception {
        Director director = new Director(); Subspace subspace = new Subspace(); Info info = new Info();
        PinnedPanels panels = new PinnedPanels(); panels.bindCaptionOwner(director);
        panels.pulse(true); panels.add(42, subspace, info); Handler.runDue();
        check(panels.getError().isEmpty());
        Transform transform = subspace.graph.transform;
        check(Boolean.TRUE.equals(transform.last[0]) && Boolean.TRUE.equals(transform.last[1]));
        check(transform.reformSizes.minWidth == .3f && transform.reformSizes.minHeight == .2f);
        check(transform.reformSizes.maxWidth == 3f && transform.reformSizes.maxHeight == 2f);
        check(Math.abs(transform.reformOptions.boundaryWidthMeters - .176f) < .00001f);
        SystemClock.now += 2910; Handler.runDue(); // The observed busy-launch gap must not revoke the panel lease.
        Channel<Size> resized = emit(subspace, 1000, 750, 0); Handler.runDue();
        check(director.taskOperations.calls == 1);
        AtomicInteger pending = (AtomicInteger) PinnedPanels.field(panels, "resizeCompletions");
        check(pending.get() == 1); Size actual = receive(resized); check(pending.get() == 0);
        check(actual.getWidth() == 1000 && actual.getHeight() == 750);
        info.configuration.windowConfiguration.bounds = new Rect(0, 0, 1000, 750);
        panels.updateInfo(42, info); Handler.runDue(); check((Float) transform.last[3] == 1f);
        check(subspace.events.tryEmit(new Object())); check(director.taskOperations.calls == 1);
        info.isResizeable = false; panels.updateInfo(42, info); Handler.runDue();
        check(Boolean.FALSE.equals(transform.last[1]));
        check(receive(emit(subspace, 1100, 800, 1)) == null); check(director.taskOperations.calls == 1);
        panels.shutdown(); Handler.runDue(); check(panels.isRestored());
        check(transform.reformSizes.minWidth == null && transform.reformSizes.minHeight == .12f);
        check(transform.reformSizes.maxWidth == 2f && transform.reformSizes.maxHeight == null);
        check(transform.reformOptions.boundaryWidthMeters == .04f && transform.reformOptions.boundaryCornerRadiusMeters == .03f);
        check(Boolean.FALSE.equals(transform.last[0]) && Boolean.FALSE.equals(transform.last[1]));
        check(transform.transformListenerFactory.closes == 1 && subspace.events.getSubscriptionCount().getValue() == 0);

        Director delayed = new Director(); delayed.taskOperations.automatic = false;
        Subspace second = new Subspace(); AtomicInteger inflight = new AtomicInteger();
        ArrayList<Exception> errors = new ArrayList<>();
        PinnedResize helper = new PinnedResize(delayed, second, new Info(), delayed.mainHandler, inflight, () -> true, errors::add);
        resized = emit(second, 900, 700, 1); check(inflight.get() == 1);
        helper.close(); delayed.taskOperations.callback.invoke(new Rect(0, 0, 890, 690)); Handler.runDue();
        actual = receive(resized); check(actual.getWidth() == 890 && actual.getHeight() == 690);
        check(inflight.get() == 0 && errors.isEmpty());

        Director timed = new Director(); timed.taskOperations.automatic = false; Subspace third = new Subspace();
        helper = new PinnedResize(timed, third, new Info(), timed.mainHandler, inflight, () -> true, errors::add);
        resized = emit(third, 900, 700, 1); SystemClock.now += 5001; Handler.runDue();
        check(receive(resized) == null && inflight.get() == 0 && errors.size() == 1);
        timed.taskOperations.callback.invoke(new Rect(0, 0, 900, 700)); Handler.runDue();
        check(inflight.get() == 0 && errors.size() == 1); helper.close();

        Director failed = new Director(); failed.taskOperations.throwsOnResize = true; Subspace fourth = new Subspace();
        helper = new PinnedResize(failed, fourth, new Info(), failed.mainHandler, inflight, () -> true, errors::add);
        check(receive(emit(fourth, 900, 700, 1)) == null && inflight.get() == 0 && errors.size() == 2);
        helper.close();
        Director rejected = new Director(); Subspace fifth = new Subspace();
        helper = new PinnedResize(rejected, fifth, new Info(), rejected.mainHandler, inflight, () -> false, errors::add);
        check(receive(emit(fifth, 900, 700, 1)) == null && rejected.taskOperations.calls == 0);
        helper.close();
        System.out.println("PASS: pinned resize limits/rollback, stock bounds commit, focus isolation, acknowledgement, timeout and cleanup");
    }
}
""",
})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", required=True, type=Path)
    parser.add_argument("--ecj", required=True, type=Path)
    parser.add_argument("--sdk-tools-lib", required=True, type=Path)
    args = parser.parse_args()
    kotlin = sorted(args.sdk_tools_lib.glob("external/org/jetbrains/kotlin/kotlin-stdlib/*/*.jar"))
    coroutines = sorted(args.sdk_tools_lib.glob("external/org/jetbrains/kotlinx/kotlinx-coroutines-core-jvm/*/*.jar"))
    if not kotlin or not coroutines:
        parser.error("Android command-line tools must include Kotlin stdlib and coroutines for this host check")
    classpath = ":".join(str(path) for path in (kotlin[-1], coroutines[-1]))
    with tempfile.TemporaryDirectory(prefix="gxr-pinned-panels-host-") as temporary:
        work = Path(temporary)
        paths = []
        for name, source in SOURCES.items():
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)
            paths.append(path)
        production = ROOT / "modules/window-controls/android/local/gxr/pins"
        paths.extend(production / name for name in ("PinnedPanels.java", "PinnedResize.java", "FadePolicy.java", "PanelRay.java", "BackdropPolicy.java"))
        paths.append(ROOT / "modules/window-rotation/android/local/gxr/rotation/WindowFeatures.java")
        output = work / "classes"
        subprocess.run([str(args.java), "-jar", str(args.ecj), "-source", "1.8", "-target", "1.8", "-proc:none",
                        "-cp", classpath, "-d", str(output), *(str(path) for path in paths)], check=True)
        subprocess.run([str(args.java), "-cp", str(output) + ":" + classpath, "local.gxr.pins.PinnedPanelsTest"], check=True, timeout=20)


if __name__ == "__main__":
    main()
