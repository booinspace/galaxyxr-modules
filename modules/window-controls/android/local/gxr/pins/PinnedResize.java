package local.gxr.pins;

import android.graphics.Rect;
import android.os.Handler;
import android.util.Size;
import java.io.Closeable;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.concurrent.CancellationException;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.BooleanSupplier;
import java.util.function.Consumer;

/** Commits only resize events; overlay pins must not request Home Space's app focus. */
final class PinnedResize implements Closeable {
    private final Object operations;
    private final Object token;
    private final Handler owner;
    private final AtomicInteger pending;
    private final BooleanSupplier eligible;
    private final Consumer<Exception> failure;
    private final ClassLoader loader;
    private final Class<?> continuation;
    private final Class<?> function1;
    private final Class<?> boundsEvent;
    private final Object unit;
    private final Object suspended;
    private final Method send;
    private Object job;
    private volatile boolean closed;

    PinnedResize(Object director, Object subspace, Object info, Handler owner, AtomicInteger pending,
            BooleanSupplier eligible, Consumer<Exception> failure) throws Exception {
        this.owner = owner;
        this.pending = pending;
        this.eligible = eligible;
        this.failure = failure;
        operations = PinnedPanels.field(director, "taskOperations");
        token = info.getClass().getField("token").get(info);
        loader = subspace.getClass().getClassLoader();
        continuation = loader.loadClass("kotlin.coroutines.Continuation");
        function1 = loader.loadClass("kotlin.jvm.functions.Function1");
        Class<?> function2 = loader.loadClass("kotlin.jvm.functions.Function2");
        Class<?> flow = loader.loadClass("kotlinx.coroutines.flow.Flow");
        Class<?> flowKt = loader.loadClass("kotlinx.coroutines.flow.FlowKt");
        boundsEvent = loader.loadClass("com.android.systemui.xr.spatial.TaskSubspace$PanelBoundsChangeEvent");
        unit = loader.loadClass("kotlin.Unit").getField("INSTANCE").get(null);
        suspended = staticCall(loader.loadClass("kotlin.coroutines.intrinsics.IntrinsicsKt"),
                "getCOROUTINE_SUSPENDED", new Class<?>[0]);
        send = loader.loadClass("kotlinx.coroutines.channels.SendChannel").getMethod("send", Object.class, continuation);
        Object action = Proxy.newProxyInstance(loader, new Class<?>[] {function2}, (proxy, method, args) -> {
            if (!method.getName().equals("invoke")) return objectMethod(proxy, method, args);
            if (!boundsEvent.isInstance(args[0])) return unit;
            try { return resize(args[0], args[1]); }
            catch (Exception error) { failure.accept(error); return unit; }
        });
        Object events = staticCall(flowKt, "onEach", new Class<?>[] {flow, function2},
                PinnedPanels.get(subspace, "getEvents"), action);
        job = staticCall(flowKt, "launchIn", new Class<?>[] {flow, loader.loadClass("kotlinx.coroutines.CoroutineScope")},
                events, PinnedPanels.field(director, "coroutineScope"));
    }

    private static Object staticCall(Class<?> owner, String name, Class<?>[] types, Object... args) throws Exception {
        Method method = owner.getMethod(name, types);
        method.setAccessible(true);
        return method.invoke(null, args);
    }

    private static Object objectMethod(Object proxy, Method method, Object[] args) {
        if (method.getName().equals("hashCode")) return System.identityHashCode(proxy);
        if (method.getName().equals("equals")) return proxy == args[0];
        return "PinnedResize";
    }

    private Object resize(Object event, Object receiver) throws Exception {
        int width = ((Number) PinnedPanels.get(event, "getNewWidthPx")).intValue();
        int height = ((Number) PinnedPanels.get(event, "getNewHeightPx")).intValue();
        Object intercepted = staticCall(loader.loadClass("kotlin.coroutines.intrinsics.IntrinsicsKt"),
                "intercepted", new Class<?>[] {continuation}, receiver);
        Object safe = loader.loadClass("kotlin.coroutines.SafeContinuation").getConstructor(continuation).newInstance(intercepted);
        Object channel = PinnedPanels.get(event, "getOnComplete");
        AtomicBoolean completed = new AtomicBoolean(), acknowledged = new AtomicBoolean();
        pending.incrementAndGet();
        Consumer<Object> acknowledge = result -> {
            if (!acknowledged.compareAndSet(false, true)) return;
            try { PinnedPanels.call(safe, "resumeWith", new Class<?>[] {Object.class}, result); }
            catch (Exception error) { failure.accept(error); }
            finally { pending.decrementAndGet(); }
        };
        Object ack = Proxy.newProxyInstance(loader, new Class<?>[] {continuation}, (proxy, method, args) -> {
            if (method.getName().equals("getContext")) return PinnedPanels.get(safe, "getContext");
            if (method.getName().equals("resumeWith")) { acknowledge.accept(args[0]); return null; }
            return objectMethod(proxy, method, args);
        });
        Consumer<Rect> finish = bounds -> {
            if (!completed.compareAndSet(false, true)) return;
            Size actual = bounds != null && bounds.width() > 0 && bounds.height() > 0
                    ? new Size(bounds.width(), bounds.height()) : null;
            try {
                Object result = send.invoke(channel, actual, ack);
                if (result != suspended) acknowledge.accept(unit);
            } catch (Exception error) {
                acknowledge.accept(unit);
                failure.accept(error);
            }
        };
        Runnable timeout = () -> {
            if (completed.get()) return;
            finish.accept(null);
            if (!closed) failure.accept(new IllegalStateException("Pinned resize did not complete within five seconds"));
        };
        Object callback = Proxy.newProxyInstance(loader, new Class<?>[] {function1}, (proxy, method, args) -> {
            if (!method.getName().equals("invoke")) return objectMethod(proxy, method, args);
            Rect bounds = args[0] == null ? null : new Rect((Rect) args[0]);
            if (!owner.post(() -> { owner.removeCallbacks(timeout); finish.accept(bounds); })) finish.accept(null);
            return unit;
        });
        try {
            if (closed || !eligible.getAsBoolean() || width <= 0 || height <= 0 || width > 32768 || height > 32768) {
                finish.accept(null);
            } else {
                if (!owner.postDelayed(timeout, 5000)) throw new IllegalStateException("Resize owner stopped");
                PinnedPanels.call(operations, "resizeTask",
                        new Class<?>[] {loader.loadClass("android.window.WindowContainerToken"), Size.class, function1},
                        token, new Size(width, height), callback);
            }
        } catch (Exception error) {
            owner.removeCallbacks(timeout);
            finish.accept(null);
            failure.accept(error);
        }
        return PinnedPanels.get(safe, "getOrThrow");
    }

    @Override public void close() throws java.io.IOException {
        closed = true;
        if (job == null) return;
        try {
            loader.loadClass("kotlinx.coroutines.Job").getMethod("cancel", CancellationException.class)
                    .invoke(job, new Object[] {null});
            job = null;
        } catch (Exception error) { throw new java.io.IOException("Cannot stop pinned resize events", error); }
    }
}
