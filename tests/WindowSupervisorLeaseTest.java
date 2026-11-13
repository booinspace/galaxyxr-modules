import android.graphics.CPM;
import java.lang.reflect.Field;
import local.gxr.curvature.CurvatureLease;
import local.gxr.curvature.CurvatureSession;

/** A busy launch may delay renewal; loss of the supervisor must still restore the task. */
public final class WindowSupervisorLeaseTest {
    private static final class Fake implements CurvatureLease.Clock, CurvatureLease.Sink {
        long now = 100;
        float applied;
        public long milliseconds() { return now; }
        public void apply(float value) { applied = value; }
    }
    private static void check(boolean condition) { if (!condition) throw new AssertionError(); }

    public static void main(String[] args) throws Exception {
        long expected = Long.parseLong(args[0]);
        check(expected == 5000);
        try (CurvatureSession session = CurvatureSession.supervised(42, new CPM.Node())) {
            Field leaseField = CurvatureSession.class.getDeclaredField("lease");
            leaseField.setAccessible(true);
            Field duration = CurvatureLease.class.getDeclaredField("leaseMs");
            duration.setAccessible(true);
            check(duration.getLong(leaseField.get(session)) == expected);
        }
        Fake fake = new Fake();
        try (CurvatureLease lease = CurvatureLease.supervised(fake, fake, expected)) {
            lease.set(.5f);
            fake.now += 2910;
            lease.tick(); check(fake.applied == .5f && lease.heartbeat());
            fake.now += expected - 1;
            lease.tick(); check(fake.applied == .5f);
            fake.now++;
            lease.tick(); check(fake.applied == 0 && "restored".equals(lease.getStatus()));
            check(!lease.heartbeat());
        }
        System.out.println("PASS: busy-launch renewal, matching session watchdog and five-second loss-of-supervisor rollback");
    }
}
