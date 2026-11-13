package local.gxr.pins;

public final class PinRequestTest {
    private static void fails(Runnable action) {
        try { action.run(); }
        catch (IllegalArgumentException | IllegalStateException expected) { return; }
        throw new AssertionError("Unsafe pin request accepted");
    }
    public static void main(String[] ignored) {
        PinRequest request = new PinRequest(1000, 42, "app.symfonik.music.player");
        if (PinRequest.confirmed(1000, -1) || PinRequest.confirmed(999, 1000) ||
                PinRequest.confirmed(6001, 1000) || !PinRequest.confirmed(1001, 1000) ||
                !PinRequest.confirmed(6000, 1000)) throw new AssertionError("Unsafe reopen confirmation");
        if (!request.toWire().equals("1000 42 app.symfonik.music.player")) throw new AssertionError();
        request.requireFresh(1000);
        request.requireFresh(16000);
        fails(() -> request.requireFresh(999));
        fails(() -> request.requireFresh(16001));
        fails(() -> new PinRequest(-1, 42, "app.valid"));
        fails(() -> new PinRequest(1000, 0, "app.valid"));
        fails(() -> new PinRequest(1000, -1, "app.valid"));
        for (String pkg : new String[] {null, "", "app", "app.valid;id", "app.valid\nother", "app.*", "app..valid", "app.$(id)"}) {
            fails(() -> new PinRequest(1000, 42, pkg));
        }
        StringBuilder large = new StringBuilder("app.");
        for (int index = 0; index < 200; index++) large.append('a');
        fails(() -> new PinRequest(1000, 42, large.toString()));
        PinRequest nearLimit = new PinRequest(Long.MAX_VALUE - 1, Integer.MAX_VALUE, "app.valid");
        nearLimit.requireFresh(Long.MAX_VALUE);
        System.out.println("Pin requests: task identity, age, rollback, overflow and shell text rejection passed");
    }
}
