package local.gxr.rotation;

/** Local yaw(Y), pitch(X), roll(Z), composed Y * X * Z; scalar component first. */
public final class RotationMath {
    private RotationMath() { }

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
