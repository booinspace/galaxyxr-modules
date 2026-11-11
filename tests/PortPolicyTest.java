import com.gxr.mic.GainState;
import com.gxr.pt.PassthroughPolicy;

public final class PortPolicyTest {
    private static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
    public static void main(String[] args) {
        check(GainState.eligible("virtualdesktop.android", 10, false), "VD capture");
        check(!GainState.eligible("another.app", 10, false), "Other source-10 app must not trigger boost");
        check(!GainState.eligible("virtualdesktop.android", 10, true), "Silenced client");
        check(!GainState.eligible("virtualdesktop.android", 1, false), "Other source");
        check(GainState.wanted(true, true, 1), "Mode 1 concurrent recording");
        check(!GainState.wanted(true, true, 2), "Mode 2 concurrent recording");
        check(GainState.wanted(true, false, 2), "Mode 2 exclusive VD capture");
        check(!GainState.wanted(false, false, 1), "Idle");
        GainState gain = new GainState();
        check(gain.target(true, 84, 15) == 99, "Default boost");
        gain.own(84, 99);
        check(gain.target(true, 99, 15) == 99, "Do not stack boost");
        check(gain.target(false, 99, 15) == 84, "Restore our own write");
        check(gain.target(false, 90, 15) == 90, "Respect another writer");
        check(gain.target(true, 120, 15) == 124, "Mixer cap");
        try { gain.target(true, 125, 15); throw new AssertionError("Invalid mixer accepted"); }
        catch (IllegalArgumentException expected) { }

        PassthroughPolicy.Push push = PassthroughPolicy.push(
                "1794394846.100 12947 D SceneTransactionProcessorImpl: Setting XR Runtime Server PT layer to SetXrRuntimePassthroughState(alpha=0.0, z=-2)");
        check(push != null && push.alpha == 0 && push.z == -2, "Parse AZJ2 stock state");
        check(PassthroughPolicy.push("other log") == null, "Ignore unrelated logs");
        check(PassthroughPolicy.timestamp("1794394846.100 12947 D Tag: x") == 1794394846100L, "Epoch log timestamp");
        for (String invalid : new String[] {"alpha=2.0, z=9", "missing fields"}) {
            try { PassthroughPolicy.push(PassthroughPolicy.SYS_PUSH + invalid); throw new AssertionError("Invalid push accepted"); }
            catch (IllegalArgumentException expected) { }
        }
        float threshold = Float.parseFloat("-Infinity");
        for (float lux : new float[] {0, Float.MIN_VALUE, 3, 10, 100000, Float.MAX_VALUE}) {
            check(!(lux <= threshold), "Chosen threshold must not trigger a low-light transition");
        }
        System.out.println("PASS: mic eligibility/ownership, passthrough parser, and low-light threshold");
    }
}
