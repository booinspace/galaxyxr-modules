package local.gxr.workspaces;

import java.util.concurrent.Callable;

/** Wait for a window without treating slow startup as failure; the caller owns health and cancellation. */
public final class WorkspaceWait {
    private WorkspaceWait() {}
    public interface Step { void run() throws Exception; }
    public static <T> T untilReady(Callable<T> probe, Step healthy, Step idle) throws Exception {
        while (true) {
            healthy.run();
            T result = probe.call();
            if (result != null) return result;
            idle.run();
        }
    }
}
