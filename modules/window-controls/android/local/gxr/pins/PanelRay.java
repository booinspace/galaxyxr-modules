package local.gxr.pins;

/** Converts a world-space gaze ray to the reference node's local coordinates. */
public final class PanelRay {
    private PanelRay() { }

    public static boolean hitsPanel(float[] ray, float width, float height) {
        if (ray == null || ray.length != 6 || !Float.isFinite(width) || !Float.isFinite(height) ||
                width <= 0 || height <= 0) return false;
        for (float value : ray) if (!Float.isFinite(value)) return false;
        if (Math.abs(ray[5]) < .0001f) return false;
        float distance = -ray[2] / ray[5];
        if (!Float.isFinite(distance) || distance <= 0) return false;
        float x = ray[0] + distance * ray[3], y = ray[1] + distance * ray[4];
        // The stock caption pill sits just above the app's centred rectangle.
        return Math.abs(x) <= width / 2 && y >= -height / 2 && y <= height / 2 + .08f;
    }

    public static float[] toLocal(float[] matrix, float[] ray) {
        if (matrix == null || matrix.length != 16 || ray == null || ray.length != 6) return null;
        for (float value : matrix) if (!Float.isFinite(value)) return null;
        for (float value : ray) if (!Float.isFinite(value)) return null;
        if (Math.abs(matrix[3]) > .0001f || Math.abs(matrix[7]) > .0001f ||
                Math.abs(matrix[11]) > .0001f || Math.abs(matrix[15] - 1) > .0001f) return null;
        // CPM matrices are column-major affine transforms, including panel scale.
        float a = matrix[0], b = matrix[4], c = matrix[8];
        float d = matrix[1], e = matrix[5], f = matrix[9];
        float g = matrix[2], h = matrix[6], i = matrix[10];
        float[] inverse = {e*i-f*h, c*h-b*i, b*f-c*e,
                f*g-d*i, a*i-c*g, c*d-a*f, d*h-e*g, b*g-a*h, a*e-b*d};
        float determinant = a * inverse[0] + b * inverse[3] + c * inverse[6];
        if (!Float.isFinite(determinant) || Math.abs(determinant) < .000001f) return null;
        float[] local = new float[6];
        float x = ray[0] - matrix[12], y = ray[1] - matrix[13], z = ray[2] - matrix[14];
        for (int row = 0; row < 3; row++) {
            int at = row * 3;
            local[row] = (inverse[at]*x + inverse[at+1]*y + inverse[at+2]*z) / determinant;
            local[row+3] = (inverse[at]*ray[3] + inverse[at+1]*ray[4] + inverse[at+2]*ray[5]) / determinant;
        }
        float length = (float) Math.sqrt(local[3]*local[3] + local[4]*local[4] + local[5]*local[5]);
        if (!Float.isFinite(length) || length < .000001f) return null;
        for (int at = 3; at < 6; at++) local[at] /= length;
        for (float value : local) if (!Float.isFinite(value)) return null;
        return local;
    }
}
