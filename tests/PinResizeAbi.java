import java.lang.reflect.Method;
import java.lang.reflect.Proxy;

/** Read-only AZJ2 reflection check, run in a disposable app_process with the stock APK. */
public final class PinResizeAbi {
    private static Class<?> type(String name) throws Exception { return Class.forName(name); }
    private static Object invoke(Class<?> owner, Object target, String name, Class<?>[] types, Object... args) throws Exception {
        Method method = owner.getMethod(name, types);
        method.setAccessible(true);
        return method.invoke(target, args);
    }
    public static void main(String[] args) throws Exception {
        Class<?> director = type("com.android.wm.shell.windowdecor.XrCaptionWindowDecorDirector");
        for (String field : new String[] {"mainHandler", "context", "coroutineScope", "taskOperations", "taskOrganizer"}) director.getDeclaredField(field);
        director.getDeclaredField("taskOrganizer").getType().getMethod("getRunningTasks", int.class);
        type("android.app.ActivityTaskManager").getMethod("getService");
        type("android.app.IActivityTaskManager").getMethod("setFocusedTask", int.class);
        Class<?> info = type("android.app.ActivityManager$RunningTaskInfo");
        for (String field : new String[] {"configuration", "token", "minWidth", "minHeight", "defaultMinSize", "isResizeable",
                "taskId", "userId", "xrDesktopMode", "isFocused", "isVisible", "isVisibleRequested"}) info.getField(field);
        Class<?> dp = type("com.android.systemui.xr.ui.unit.Dp"); dp.getConstructor(float.class);
        Class<?> metrics = type("com.android.systemui.xr.ui.DisplayMetrics");
        metrics.getMethod("toPx", dp); metrics.getMethod("getDpToMeter", int.class); metrics.getMethod("getPixelsPerMeter");
        Class<?> sizes = type("com.android.systemui.xr.spatial.impl.TaskSizes");
        sizes.getMethod("buildMinimumTaskSize", type("android.content.Context"), Integer.class, Integer.class, Integer.class);
        sizes.getMethod("buildMaximumTaskSize", type("android.content.Context"));
        Class<?> transform = type("com.android.systemui.xr.spatial.SpaceFlingerTransformNode");
        Class<?> limits = transform.getDeclaredField("reformSizes").getType();
        for (String field : new String[] {"MinWidthMeters", "MinHeightMeters", "MaxWidthMeters", "MaxHeightMeters"}) {
            limits.getMethod("get" + field); limits.getMethod("set" + field, Float.class);
        }
        Class<?> options = transform.getDeclaredField("reformOptions").getType();
        options.getField("boundaryWidthMeters"); options.getField("boundaryCornerRadiusMeters");
        Class<?> continuation = type("kotlin.coroutines.Continuation");
        Object unit = type("kotlin.Unit").getField("INSTANCE").get(null);
        Object empty = type("kotlin.coroutines.EmptyCoroutineContext").getField("INSTANCE").get(null);
        Object receiver = Proxy.newProxyInstance(PinResizeAbi.class.getClassLoader(), new Class<?>[] {continuation},
                (proxy, method, values) -> method.getName().equals("getContext") ? empty : null);
        Class<?> intrinsics = type("kotlin.coroutines.intrinsics.IntrinsicsKt");
        invoke(intrinsics, null, "getCOROUTINE_SUSPENDED", new Class<?>[0]);
        receiver = invoke(intrinsics, null, "intercepted", new Class<?>[] {continuation}, receiver);
        Class<?> safeType = type("kotlin.coroutines.SafeContinuation");
        Object safe = safeType.getConstructor(continuation).newInstance(receiver);
        invoke(safeType, safe, "resumeWith", new Class<?>[] {Object.class}, unit);
        if (invoke(safeType, safe, "getOrThrow", new Class<?>[0]) != unit) throw new AssertionError("Continuation ABI");
        type("kotlinx.coroutines.channels.SendChannel").getMethod("send", Object.class, continuation);
        Class<?> function1 = type("kotlin.jvm.functions.Function1");
        director.getDeclaredField("taskOperations").getType().getMethod("resizeTask",
                type("android.window.WindowContainerToken"), type("android.util.Size"), function1);
        Class<?> bounds = type("com.android.systemui.xr.spatial.TaskSubspace$PanelBoundsChangeEvent");
        for (String name : new String[] {"getNewWidthPx", "getNewHeightPx", "getOnComplete"}) bounds.getMethod(name);
        type("com.android.systemui.xr.spatial.TaskSubspace").getMethod("getEvents");
        Class<?> flow = type("kotlinx.coroutines.flow.Flow"), flowKt = type("kotlinx.coroutines.flow.FlowKt");
        Class<?> function2 = type("kotlin.jvm.functions.Function2");
        int[] calls = {0};
        Object action = Proxy.newProxyInstance(PinResizeAbi.class.getClassLoader(), new Class<?>[] {function2}, (proxy, method, values) -> {
            if (method.getName().equals("invoke")) { calls[0]++; return unit; }
            if (method.getName().equals("hashCode")) return System.identityHashCode(proxy);
            if (method.getName().equals("equals")) return proxy == values[0];
            return "ResizeAbi";
        });
        Object events = invoke(flowKt, null, "flowOf", new Class<?>[] {Object.class}, unit);
        events = invoke(flowKt, null, "onEach", new Class<?>[] {flow, function2}, events, action);
        Object dispatcher = invoke(type("kotlinx.coroutines.Dispatchers"), null, "getUnconfined", new Class<?>[0]);
        Object scope = invoke(type("kotlinx.coroutines.CoroutineScopeKt"), null, "CoroutineScope",
                new Class<?>[] {type("kotlin.coroutines.CoroutineContext")}, dispatcher);
        Object job = invoke(flowKt, null, "launchIn", new Class<?>[] {flow, type("kotlinx.coroutines.CoroutineScope")}, events, scope);
        invoke(type("kotlinx.coroutines.Job"), job, "cancel", new Class<?>[] {java.util.concurrent.CancellationException.class}, new Object[] {null});
        if (calls[0] != 1) throw new AssertionError("Flow did not run exactly once");
        System.out.println("RESIZE_ABI_PASS stock resize/limits, SafeContinuation and Flow; no SystemUI attachment or window changes");
    }
}
