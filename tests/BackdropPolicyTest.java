package local.gxr.pins;

public final class BackdropPolicyTest {
    public static void main(String[] ignored) {
        for (int mask = 0; mask < 128; mask++) {
            boolean actual = BackdropPolicy.allows((mask & 1) != 0, (mask & 2) != 0,
                    (mask & 4) != 0, (mask & 8) != 0, (mask & 16) != 0,
                    (mask & 32) != 0, (mask & 64) != 0);
            if (actual != (mask == (1 | 4 | 8 | 32))) throw new AssertionError("Unsafe scope: " + mask);
        }
        System.out.println("Backdrop policy: 128 scope combinations, protected UI and unknown state passed");
    }
}
