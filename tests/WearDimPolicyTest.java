import com.gxr.wear.DimPolicy;

public final class WearDimPolicyTest {
    private static void check(boolean value) {
        if (!value) throw new AssertionError();
    }

    public static void main(String[] args) {
        DimPolicy policy = new DimPolicy();
        check(!policy.update(1000, true, true, 1, true));
        check(!policy.update(60999, true, true, 1, true));
        check(policy.update(61000, true, true, 1, true));
        check(!policy.update(61001, true, true, 0, true));
        check(!policy.update(62000, true, true, 1, true));
        check(!policy.update(121999, true, true, 1, true));
        check(!policy.update(122000, false, true, 1, true));
        check(!policy.update(200000, true, false, 1, true));
        check(!policy.update(300000, true, true, -1, true));
        check(!policy.update(400000, true, true, 2, true));
        check(!policy.update(500000, true, true, 1, true));
        check(policy.update(560000, true, true, 1, true));
        check(policy.update(560500, true, true, 2, false)); // No changed snapshot retains the last state.
        check(policy.update(621001, true, true, 2, false)); // Steady input is not lost tracking.
        check(!policy.update(621003, true, true, 2, true)); // Unknown eyes restore immediately.
        check(!policy.update(621004, true, true, 1, true));
        check(policy.update(681004, true, true, 1, true));
        check(!policy.update(681005, true, false, 1, true)); // Never wake a stock sleeping headset.
        check(!policy.update(681006, true, true, 1, false)); // Rewear needs a new confirmed state.
        System.out.println("WearDimPolicyTest passed");
    }
}
