package local.gxr.workspaces;

/** Column-major affine transforms, matching AZJ2's CPM node listener. */
public final class WorkspaceMath {
    private WorkspaceMath() {}
    public static float[] identity() { return new float[] {1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1}; }
    public static float[] checked(float[] m) {
        if (m == null || m.length != 16) throw new IllegalArgumentException("Missing spatial pose");
        for (float v : m) if (!Float.isFinite(v) || Math.abs(v) > 100000) throw new IllegalArgumentException("Invalid spatial pose");
        if (Math.abs(m[3]) > .001 || Math.abs(m[7]) > .001 || Math.abs(m[11]) > .001 || Math.abs(m[15] - 1) > .001) {
            throw new IllegalArgumentException("Expected an affine spatial pose");
        }
        if (Math.abs(m[12]) > 100 || Math.abs(m[13]) > 100 || Math.abs(m[14]) > 100) throw new IllegalArgumentException("Workspace is too far away");
        double determinant = m[0] * (m[5] * m[10] - m[9] * m[6])
                - m[4] * (m[1] * m[10] - m[9] * m[2]) + m[8] * (m[1] * m[6] - m[5] * m[2]);
        if (Math.abs(determinant) < 1e-12) throw new IllegalArgumentException("Singular spatial pose");
        return m.clone();
    }
    public static float[] multiply(float[] a, float[] b) {
        checked(a); checked(b);
        float[] out = new float[16];
        for (int col = 0; col < 4; col++) for (int row = 0; row < 4; row++) {
            for (int k = 0; k < 4; k++) out[col*4+row] += a[k*4+row] * b[col*4+k];
        }
        return checked(out);
    }
    public static float[] inverse(float[] matrix) {
        float[] m = checked(matrix);
        double[][] a = new double[4][8];
        for (int r = 0; r < 4; r++) for (int c = 0; c < 4; c++) { a[r][c] = m[c*4+r]; a[r][c+4] = r == c ? 1 : 0; }
        for (int c = 0; c < 4; c++) {
            int pivot = c;
            for (int r = c+1; r < 4; r++) if (Math.abs(a[r][c]) > Math.abs(a[pivot][c])) pivot = r;
            if (Math.abs(a[pivot][c]) < 1e-9) throw new IllegalArgumentException("Singular spatial pose");
            double[] swap = a[c]; a[c] = a[pivot]; a[pivot] = swap;
            double divisor = a[c][c];
            for (int k = 0; k < 8; k++) a[c][k] /= divisor;
            for (int r = 0; r < 4; r++) if (r != c) {
                double factor = a[r][c];
                for (int k = 0; k < 8; k++) a[r][k] -= factor * a[c][k];
            }
        }
        float[] out = new float[16];
        for (int r = 0; r < 4; r++) for (int c = 0; c < 4; c++) out[c*4+r] = (float) a[r][c+4];
        return checked(out);
    }
    public static float[] relative(float[] anchor, float[] world) { return multiply(inverse(anchor), world); }
    public static float[] restore(float[] anchor, float[] relative) { return multiply(anchor, relative); }
}
