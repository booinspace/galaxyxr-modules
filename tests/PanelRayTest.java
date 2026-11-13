package local.gxr.pins;

public final class PanelRayTest {
    private static final float[] IDENTITY = {1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1};
    private static void equal(float[] actual, float... expected) {
        if (actual == null || actual.length != expected.length) throw new AssertionError("Missing ray");
        for (int i = 0; i < actual.length; i++) {
            if (Math.abs(actual[i] - expected[i]) > .0001f) throw new AssertionError("Wrong coordinate at " + i);
        }
    }
    private static void rejects(float[] matrix, float[] ray) {
        if (PanelRay.toLocal(matrix, ray) != null) throw new AssertionError("Invalid transform accepted");
    }
    private static void hit(float[] ray, boolean expected) {
        if (PanelRay.hitsPanel(ray, 1, 1) != expected) throw new AssertionError("Wrong panel attention");
    }
    public static void main(String[] ignored) {
        float[] ray = {.2f, -.3f, 2, 0, 0, -1};
        equal(PanelRay.toLocal(IDENTITY, ray), ray);
        hit(ray, true);
        hit(new float[] {.51f, 0, 2, 0, 0, -1}, false);
        hit(new float[] {-.51f, 0, 2, 0, 0, -1}, false);
        hit(new float[] {0, -.51f, 2, 0, 0, -1}, false);
        hit(new float[] {0, .56f, 2, 0, 0, -1}, true); // Caption above the app remains attended.
        hit(new float[] {0, .59f, 2, 0, 0, -1}, false);
        hit(new float[] {0, 0, 2, 0, 0, 1}, false);
        hit(new float[] {0, 0, 2, 1, 0, 0}, false);
        hit(new float[] {0, 0, 0, 0, 0, -1}, false);
        hit(new float[] {0, 0, -2, 0, 0, 1}, true);
        hit(new float[] {Float.NaN, 0, 2, 0, 0, -1}, false);
        hit(null, false);
        hit(new float[5], false);
        for (float invalidSize : new float[] {0, -1, Float.NaN, Float.POSITIVE_INFINITY}) {
            if (PanelRay.hitsPanel(ray, invalidSize, 1) || PanelRay.hitsPanel(ray, 1, invalidSize)) {
                throw new AssertionError("Invalid panel bounds accepted");
            }
        }
        // Translation, a quarter turn, and nonuniform scale must all be inverted.
        float[] moved = {0,2,0,0, -3,0,0,0, 0,0,4,0, 5,6,-7,1};
        equal(PanelRay.toLocal(moved, new float[] {5.9f,6.4f,1,0,0,-1}), ray);
        hit(PanelRay.toLocal(moved, new float[] {5.9f,6.4f,1,0,0,-1}), true);
        hit(PanelRay.toLocal(moved, new float[] {5.9f,7.2f,1,0,0,-1}), false);
        // Pitch and yaw change forward, not the ray's point translation.
        float[] pitched = {1,0,0,0, 0,0,1,0, 0,-1,0,0, 0,0,0,1};
        equal(PanelRay.toLocal(pitched, new float[] {.2f,-2,-.3f,0,1,0}), ray);
        hit(PanelRay.toLocal(pitched, new float[] {.2f,-2,-.3f,0,1,0}), true);
        float[] yawed = {0,0,-1,0, 0,1,0,0, 1,0,0,0, 0,0,0,1};
        equal(PanelRay.toLocal(yawed, new float[] {2,-.3f,-.2f,-1,0,0}), ray);
        hit(PanelRay.toLocal(yawed, new float[] {2,-.3f,-.2f,-1,0,0}), true);
        rejects(null, ray);
        rejects(IDENTITY, new float[5]);
        rejects(new float[16], ray);
        rejects(IDENTITY, new float[6]);
        float[] invalid = IDENTITY.clone(); invalid[4] = Float.NaN; rejects(invalid, ray);
        invalid = IDENTITY.clone(); invalid[15] = 0; rejects(invalid, ray);
        System.out.println("Panel ray: visible app/caption bounds, reference frame, pitch/yaw/roll, scale and invalid data passed");
    }
}
