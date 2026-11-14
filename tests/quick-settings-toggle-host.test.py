"""Exercise the native Java dispatch helper with deterministic Android thread/time doubles."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'android/os/Looper.java': '''package android.os;
public final class Looper { public static Looper getMainLooper() { return new Looper(); } }
''',
    'android/os/SystemClock.java': '''package android.os;
public final class SystemClock { public static long now; public static long uptimeMillis() { return now; } }
''',
    'android/os/Handler.java': '''package android.os;
import java.util.ArrayList;
public final class Handler {
    static final class Item {
        final Runnable runnable; final Object token;
        Item(Runnable runnable, Object token) { this.runnable = runnable; this.token = token; }
    }
    private static final ArrayList<Item> QUEUE = new ArrayList<>();
    public Handler(Looper looper) { }
    public boolean postAtTime(Runnable runnable, Object token, long time) { QUEUE.add(new Item(runnable, token)); return true; }
    public void removeCallbacksAndMessages(Object token) { QUEUE.removeIf(item -> item.token == token); }
    public static void drain() { while (!QUEUE.isEmpty()) QUEUE.remove(0).runnable.run(); }
    public static int pending() { return QUEUE.size(); }
}
''',
    'android/os/PowerManager.java': '''package android.os;
public final class PowerManager { public boolean interactive = true; public boolean isInteractive() { return interactive; } }
''',
    'android/content/Context.java': '''package android.content;
import android.os.PowerManager;
public final class Context {
    public static final String POWER_SERVICE = "power";
    public final PowerManager power = new PowerManager();
    public Object getSystemService(String name) { return power; }
}
''',
    'android/view/View.java': '''package android.view;
public class View { public interface OnClickListener { void onClick(View view); } }
''',
    'android/util/Log.java': '''package android.util;
public final class Log {
    public static int i(String tag, String text) { return 0; }
    public static int e(String tag, String text, Throwable failure) { return 0; }
}
''',
    'QuickSettingsToggleTest.java': '''import android.content.Context;
import android.os.Handler;
import android.os.SystemClock;
import local.gxr.controls.QuickSettingsToggle;
public final class QuickSettingsToggleTest {
    private static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
    public static void main(String[] args) {
        Context context = new Context();
        boolean[] visible = {false}, locked = {false};
        QuickSettingsToggle toggle = new QuickSettingsToggle(context, view -> {
            if (!locked[0]) visible[0] = !visible[0];
        });
        toggle.request();
        check(Handler.pending() == 0, "disabled helper must not queue work");
        toggle.setEnabled(true);
        toggle.request();
        check(!visible[0], "native action waits for the UI thread");
        Handler.drain();
        check(visible[0] && toggle.getRequests() == 1, "native action opens panel");
        toggle.request(); Handler.drain();
        check(!visible[0], "same native action closes panel using actual state");
        toggle.request(); toggle.cancel(); Handler.drain();
        check(!visible[0], "tracking loss cancels pending dispatch");
        toggle.request(); SystemClock.now = 251; Handler.drain();
        check(!visible[0], "stale main-thread work must expire");
        context.power.interactive = false;
        toggle.request(); Handler.drain();
        check(!visible[0], "screen off blocks dispatch");
        context.power.interactive = true;
        locked[0] = true;
        toggle.request(); Handler.drain();
        check(!visible[0], "existing native lockscreen check remains effective");
        toggle.request(); toggle.setEnabled(false); Handler.drain();
        check(Handler.pending() == 0, "disable cancels queued work");
        toggle.setEnabled(true); toggle.request(); toggle.close(); Handler.drain();
        toggle.setEnabled(true); toggle.request();
        check(Handler.pending() == 0, "closed helper cannot reactivate");
        QuickSettingsToggle failed = new QuickSettingsToggle(context, view -> { throw new IllegalStateException("test"); });
        failed.setEnabled(true); failed.request(); Handler.drain();
        check(!failed.getError().isEmpty(), "native action failure is isolated and reported");
        failed.request(); check(Handler.pending() == 0, "failed action disables further dispatch");
        System.out.println("PASS: native action, UI thread, stale/cancelled work, screen/lock state and cleanup");
    }
}
''',
}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--java', type=Path, required=True)
parser.add_argument('--ecj', type=Path, required=True)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='gxr-qs-toggle-test-') as directory:
    work = Path(directory)
    files = []
    for name, source in SOURCES.items():
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
        files.append(path)
    output = work / 'classes'
    subprocess.run([str(args.java), '-jar', str(args.ecj), '-source', '1.8', '-target', '1.8',
                    '-proc:none', '-failOnWarning', '-d', str(output), *(str(path) for path in files),
                    str(ROOT / 'modules/quick-settings-gesture/android/local/gxr/controls/QuickSettingsToggle.java')], check=True)
    subprocess.run([str(args.java), '-cp', str(output), 'QuickSettingsToggleTest'], check=True)
