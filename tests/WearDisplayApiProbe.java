import com.gxr.wear.DisplayPower;
import java.lang.reflect.Field;
import java.lang.reflect.Method;

/** Read-only probe: resolves panel APIs and counts eye updates, never changes power. */
public final class WearDisplayApiProbe {
    public static void main(String[] args) throws Exception {
        new DisplayPower();
        Class<?> type = Class.forName("android.graphics.CPM$SystemInputInfo");
        Object input = type.getConstructor(String.class).newInstance("GxrWearDisplayProbe");
        Method retrieve = type.getMethod("retrieveCurrentSystemInputInfo");
        Field eyes = type.getField("eyesStatus");
        int fresh = 0, present = 0, absent = 0, unknown = 0;
        for (int sample = 0; sample < 125; sample++) {
            if ((Boolean) retrieve.invoke(input)) {
                fresh++;
                int status = eyes.getInt(input);
                if (status == 0) present++;
                else if (status == 1) absent++;
                else unknown++;
            }
            Thread.sleep(16);
        }
        System.out.println("PASS: physical-display getters and power method resolved; no power writes");
        System.out.println("Eye updates: fresh=" + fresh + " present=" + present
                + " absent=" + absent + " unknown=" + unknown);
    }
}
