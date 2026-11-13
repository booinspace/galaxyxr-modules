package local.gxr.pins;

/** Fixed task identity carried from the caption button to the root supervisor. */
public final class PinRequest {
    public final long issuedAt;
    public final int taskId;
    public final String packageName;

    public PinRequest(long issuedAt, int taskId, String packageName) {
        if (issuedAt < 0 || taskId < 1 || packageName == null || packageName.length() > 200 ||
                !packageName.matches("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+")) {
            throw new IllegalArgumentException("Invalid pin request");
        }
        this.issuedAt = issuedAt;
        this.taskId = taskId;
        this.packageName = packageName;
    }

    public void requireFresh(long now) {
        if (now < issuedAt || now - issuedAt > 15000) throw new IllegalStateException("Pin request expired");
    }

    public static boolean confirmed(long now, long askedAt) {
        return askedAt >= 0 && now >= askedAt && now - askedAt <= 5000;
    }

    public String toWire() { return issuedAt + " " + taskId + " " + packageName; }
}
