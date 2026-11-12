import com.gxr.wear.DimPolicy;

public final class WearDimPolicyTest {
    private static void check(boolean value) {
        if (!value) throw new AssertionError();
    }

    public static void main(String[] args) {
        DimPolicy policy = new DimPolicy();
        check(!policy.update(1000, true, true, 1));
        check(!policy.update(60999, true, true, 1));
        check(policy.update(61000, true, true, 1));
        check(!policy.update(61001, true, true, 0));
        check(!policy.update(62000, true, true, 1));
        check(!policy.update(121999, true, true, 1));
        check(!policy.update(122000, false, true, 1));
        check(!policy.update(200000, true, false, 1));
        check(!policy.update(300000, true, true, -1));
        check(!policy.update(400000, true, true, 2));
        check(!policy.update(500000, true, true, 1));
        check(policy.update(560000, true, true, 1));
        check(Math.abs(DimPolicy.dimLevel(0.5f) - 0.1f) < 0.00001f);
        check(DimPolicy.dimLevel(0) == 0);
        for (float bad : new float[] {Float.NaN, Float.POSITIVE_INFINITY, -1, 2}) {
            boolean rejected = false;
            try { DimPolicy.dimLevel(bad); } catch (IllegalArgumentException expected) { rejected = true; }
            check(rejected);
        }
        System.out.println("WearDimPolicyTest passed");
    }
}
