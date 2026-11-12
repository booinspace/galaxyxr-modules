package local.gxr.probe;

/** Disposable ART/Frida stress test; no display, settings, app or root APIs. */
public final class CmcProbe {
    public static volatile boolean start;
    public static volatile boolean finished;
    public static int hookCalls;
    private static volatile int gcRequests;
    private static volatile Object allocation;

    public static final class Target {
        public int value(boolean enabled, int sequence) {
            if ((sequence & 7) == 0) {
                try { Thread.sleep(2); }
                catch (InterruptedException error) { throw new RuntimeException(error); }
            }
            return enabled ? sequence ^ 0x12345678 : sequence ^ 0x23456789;
        }
    }

    public static void main(String[] args) throws Exception {
        Target target = new Target();
        if (args.length != 1) throw new IllegalArgumentException("Own Gadget library path required");
        System.load(args[0]);
        System.out.println("PROBE_WAITING");
        long deadline = System.nanoTime() + 60000000000L;
        while (!start) {
            if (System.nanoTime() >= deadline) throw new IllegalStateException("Probe start timed out");
            Thread.sleep(20);
        }
        Thread collector = new Thread(() -> {
            while (!finished) {
                Runtime.getRuntime().gc();
                gcRequests++;
                try { Thread.sleep(10); }
                catch (InterruptedException ignored) { return; }
            }
        }, "CmcProbeGc");
        collector.setDaemon(true);
        collector.start();
        for (int i = 0; i < 20000; i++) {
            boolean enabled = (i & 1) != 0;
            int expected = enabled ? i ^ 0x12345678 : i ^ 0x23456789;
            if (target.value(enabled, i) != expected) throw new AssertionError("Wrong original result");
            allocation = new byte[1024];
            if (i % 5000 == 0) System.out.println("PROBE_PROGRESS " + i);
        }
        finished = true;
        collector.join(2000);
        if (hookCalls != 20000) throw new AssertionError("Hook count " + hookCalls);
        if (gcRequests < 10) throw new AssertionError("Insufficient GC overlap " + gcRequests);
        System.out.println("PROBE_PASS calls=" + hookCalls + " gcRequests=" + gcRequests);
    }
}
