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

    /** Extracts rotation from the compositor's column-major affine pose without its scale. */
    public static float[] fromMatrix(float[] matrix) {
        if (matrix == null || matrix.length != 16) throw new IllegalArgumentException("Expected a spatial pose");
        for (float value : matrix) if (!Float.isFinite(value)) throw new IllegalArgumentException("Invalid spatial pose");
        if (Math.abs(matrix[3]) > .001 || Math.abs(matrix[7]) > .001
                || Math.abs(matrix[11]) > .001 || Math.abs(matrix[15] - 1) > .001) {
            throw new IllegalArgumentException("Expected an affine spatial pose");
        }
        float[] m = matrix.clone();
        for (int column = 0; column < 3; column++) {
            int i = column * 4;
            double scale = Math.sqrt((double)m[i]*m[i] + (double)m[i+1]*m[i+1] + (double)m[i+2]*m[i+2]);
            if (scale < .000001) throw new IllegalArgumentException("Singular spatial pose");
            for (int row = 0; row < 3; row++) m[i+row] /= scale;
        }
        for (int a = 0; a < 3; a++) for (int b = a+1; b < 3; b++) {
            float dot = 0;
            for (int row = 0; row < 3; row++) dot += m[a*4+row]*m[b*4+row];
            if (Math.abs(dot) > .001) throw new IllegalArgumentException("Sheared spatial pose");
        }
        double determinant = m[0]*(m[5]*m[10]-m[9]*m[6])
                - m[4]*(m[1]*m[10]-m[9]*m[2]) + m[8]*(m[1]*m[6]-m[5]*m[2]);
        if (determinant < .999) throw new IllegalArgumentException("Reflected spatial pose");
        double w,x,y,z,trace=m[0]+m[5]+m[10];
        if (trace > 0) {
            double s=2*Math.sqrt(trace+1);w=s/4;x=(m[6]-m[9])/s;y=(m[8]-m[2])/s;z=(m[1]-m[4])/s;
        } else if (m[0] > m[5] && m[0] > m[10]) {
            double s=2*Math.sqrt(1+m[0]-m[5]-m[10]);w=(m[6]-m[9])/s;x=s/4;y=(m[4]+m[1])/s;z=(m[8]+m[2])/s;
        } else if (m[5] > m[10]) {
            double s=2*Math.sqrt(1+m[5]-m[0]-m[10]);w=(m[8]-m[2])/s;x=(m[4]+m[1])/s;y=s/4;z=(m[9]+m[6])/s;
        } else {
            double s=2*Math.sqrt(1+m[10]-m[0]-m[5]);w=(m[1]-m[4])/s;x=(m[8]+m[2])/s;y=(m[9]+m[6])/s;z=s/4;
        }
        return normalize(new float[]{(float)w,(float)x,(float)y,(float)z});
    }

    /** Converts the hand's world-space delta to the actual compositor parent's local frame. */
    public static float[] grabbed(float[] handStart, float[] handNow, float[] parentNow,
            float[] worldStart) {
        float[] delta = multiply(handNow, inverse(handStart));
        return multiply(inverse(parentNow), multiply(delta, worldStart));
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
