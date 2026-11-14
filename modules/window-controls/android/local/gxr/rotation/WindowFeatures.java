package local.gxr.rotation;

/** Shared watchdog budget; flags arrive through the root supervisor's validated stdin protocol. */
public final class WindowFeatures {
    public static final int SUPERVISOR_LEASE_MS = 5000;
    public static volatile boolean curvature = true;
    private WindowFeatures() { }
}
