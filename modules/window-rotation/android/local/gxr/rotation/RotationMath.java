package local.gxr.rotation;

/** Local yaw(Y), pitch(X), roll(Z), composed Y * X * Z; scalar component first. */
public final class RotationMath {
    private RotationMath() { }

    public static float[] normalize(float[] q) {
        if (q == null || q.length != 4) throw new IllegalArgumentException("Expected a quaternion");
        double norm = 0;
        for (float value : q) {
            if (Float.isNaN(value) || Float.isInfinite(value)) throw new IllegalArgumentException("Invalid quaternion");
            norm += value * value;
        }
        if (norm < .5 || norm > 1.5) throw new IllegalArgumentException("Quaternion is not normalized");
        float scale = (float) (1 / Math.sqrt(norm));
        return new float[] {q[0] * scale, q[1] * scale, q[2] * scale, q[3] * scale};
    }

    public static float[] inverse(float[] q) {
        float[] n = normalize(q);
        return new float[] {n[0], -n[1], -n[2], -n[3]};
    }

    public static float[] multiply(float[] a, float[] b) {
        return normalize(new float[] {
            a[0]*b[0] - a[1]*b[1] - a[2]*b[2] - a[3]*b[3],
            a[0]*b[1] + a[1]*b[0] + a[2]*b[3] - a[3]*b[2],
            a[0]*b[2] - a[1]*b[3] + a[2]*b[0] + a[3]*b[1],
            a[0]*b[3] + a[1]*b[2] - a[2]*b[1] + a[3]*b[0]
        });
    }

    /** Keeps the grabbed world orientation independent of stock parent-facing updates. */
    public static float[] grabbed(float[] handStart, float[] handNow, float[] parentStart,
            float[] parentNow, float[] localStart) {
        float[] delta = multiply(handNow, inverse(handStart));
        return multiply(inverse(parentNow), multiply(delta, multiply(parentStart, localStart)));
    }

    /** Converts the stored quaternion to the menu's Y * X * Z Euler convention. */
    public static int[] degrees(float[] value) {
        float[] q = normalize(value);
        double pitch = Math.asin(Math.max(-1, Math.min(1, 2 * (q[0]*q[1] - q[2]*q[3]))));
        double yaw = Math.atan2(2 * (q[0]*q[2] + q[1]*q[3]), 1 - 2 * (q[1]*q[1] + q[2]*q[2]));
        double roll = Math.atan2(2 * (q[0]*q[3] + q[1]*q[2]), 1 - 2 * (q[1]*q[1] + q[3]*q[3]));
        return new int[] {(int) Math.round(Math.toDegrees(pitch)), (int) Math.round(Math.toDegrees(yaw)),
            (int) Math.round(Math.toDegrees(roll))};
    }

    public static float[] orientation(float pitch, float yaw, float roll) {
        for (float value : new float[] {pitch, yaw, roll}) {
            if (Float.isNaN(value) || Float.isInfinite(value) || value < -180 || value > 180) {
                throw new IllegalArgumentException("Rotation must be finite degrees in -180..180");
            }
        }
        double p = Math.toRadians(pitch) / 2;
        double y = Math.toRadians(yaw) / 2;
        double r = Math.toRadians(roll) / 2;
        double cp = Math.cos(p), sp = Math.sin(p);
        double cy = Math.cos(y), sy = Math.sin(y);
        double cr = Math.cos(r), sr = Math.sin(r);
        return new float[] {
            (float) (cy * cp * cr + sy * sp * sr),
            (float) (cy * sp * cr + sy * cp * sr),
            (float) (sy * cp * cr - cy * sp * sr),
            (float) (cy * cp * sr - sy * sp * cr)
        };
    }
}
