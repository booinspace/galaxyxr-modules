"""Run the real root-side menu-task guard against private Android task doubles."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "android/content/ComponentName.java": """package android.content;
public final class ComponentName {
    private final String pkg;
    public ComponentName(String pkg) { this.pkg = pkg; }
    public ComponentName(String pkg, String ignored) { this(pkg); }
    public String getPackageName() { return pkg; }
    public String flattenToString() { return pkg + "/" + pkg + ".Main"; }
}
""",
    "android/app/ActivityManager.java": """package android.app;
import android.content.ComponentName;
public final class ActivityManager {
    public static final class RunningTaskInfo {
        public int taskId = 42, userId = 0, xrDesktopMode = 1;
        public android.content.Intent baseIntent;
        public boolean isVisible = true, isVisibleRequested = true;
        public ComponentName baseActivity = new ComponentName("app.valid");
        public ComponentName topActivity = baseActivity;
    }
}
""",
    "local/gxr/pins/PinMenuTaskTest.java": """package local.gxr.pins;
import android.app.ActivityManager.RunningTaskInfo;
import android.content.ComponentName;
public final class PinMenuTaskTest {
    private static final PinRequest REQUEST = new PinRequest(1000, 42, "app.valid");
    private static void rejects(RunningTaskInfo task) throws Exception {
        try { PinCli.verifyMenuTask(REQUEST, task); }
        catch (IllegalStateException expected) { return; }
        throw new AssertionError("Unrelated task was admitted");
    }
    public static void main(String[] ignored) throws Exception {
        PinCli.verifyMenuTask(REQUEST, new RunningTaskInfo());
        RunningTaskInfo task = new RunningTaskInfo(); task.taskId++; rejects(task);
        task = new RunningTaskInfo(); task.userId = 10; rejects(task);
        for (int mode : new int[] {0, 2, 3, 4, 5, 6, 7, 8}) {
            task = new RunningTaskInfo(); task.xrDesktopMode = mode; rejects(task);
        }
        task = new RunningTaskInfo(); task.baseActivity = null; rejects(task);
        task = new RunningTaskInfo(); task.topActivity = null; rejects(task);
        task = new RunningTaskInfo(); task.baseActivity = new ComponentName("other.app"); rejects(task);
        task = new RunningTaskInfo(); task.topActivity = new ComponentName("other.app"); rejects(task);
        task = new RunningTaskInfo(); task.isVisible = false; rejects(task);
        task = new RunningTaskInfo(); task.isVisibleRequested = false; rejects(task);
        task = new RunningTaskInfo();
        PinCli.requireNewWindow(java.util.Collections.singletonList(task), "app.valid", 42);
        PinCli.requireNewWindow(java.util.Collections.singletonList(task), "other.app", 0);
        try {
            PinCli.requireNewWindow(java.util.Collections.singletonList(task), "app.valid", 0);
            throw new AssertionError("A singleTask window would be reused");
        } catch (IllegalStateException expected) { }
        task.userId = 10;
        PinCli.requireNewWindow(java.util.Collections.singletonList(task), "app.valid", 0);
        PinCli.runShellCommand("sh", "-c", "[ -p /proc/$$/fd/1 ] && [ -p /proc/$$/fd/2 ] || exit 7; " +
                "i=0; while [ $i -lt 4096 ]; do printf 'launcher pipe output must keep draining\\n'; i=$((i+1)); done; " +
                "printf 'LAUNCH_STDERR_CAPTURED\\n' >&2");
        try {
            PinCli.runShellCommand("sh", "-c", "exit 17");
            throw new AssertionError("A failed launch was accepted");
        } catch (IllegalStateException expected) { }
        System.out.println("Pin task guard: exact task, owner, ordinary mode, package and visibility passed");
    }
}
""",
}

parser = argparse.ArgumentParser()
for name in ("java", "ecj", "android-jar"):
    parser.add_argument("--" + name, type=Path, required=True)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix="gxr-pin-task-check-") as directory:
    work = Path(directory)
    sources = []
    for name, text in SOURCES.items():
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        sources.append(str(path))
    sources.extend(str(ROOT / "modules/window-controls/android/local/gxr/pins" / name)
                   for name in ("PinRequest.java", "PinCli.java", "PinnedPanels.java", "PinnedResize.java", "FadePolicy.java", "BackdropPolicy.java", "PanelRay.java"))
    sources.append(str(ROOT / "modules/window-rotation/android/local/gxr/rotation/WindowFeatures.java"))
    subprocess.run([str(args.java), "-jar", str(args.ecj), "-source", "1.8", "-target", "1.8",
                    "-proc:none", "-failOnWarning", "-classpath", str(args.android_jar),
                    "-d", str(work / "classes"), *sources], check=True)
    # Force the parent's output to a file: inheritIO would fail the child's pipe assertions.
    with (work / "output.txt").open("wb") as output:
        subprocess.run([str(args.java), "-cp", str(work / "classes") + ":" + str(args.android_jar),
                        "local.gxr.pins.PinMenuTaskTest"], check=True, stdout=output,
                       stderr=subprocess.STDOUT, timeout=25)
    result = (work / "output.txt").read_text()
    assert "LAUNCH_STDERR_CAPTURED" in result
    assert result.count("launcher pipe output must keep draining") == 4096
    assert "Pin task guard:" in result
    print("Pin task and launcher: task ownership, pipe isolation, output draining and failed-exit checks passed")
