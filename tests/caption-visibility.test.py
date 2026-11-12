"""Exercise the real caption helper against a view with an enforced owner thread."""

import argparse
from pathlib import Path
import subprocess
import tempfile
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--javac", default="javac")
    parser.add_argument("--java", default="java")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        view = directory / "android/view/View.java"
        view.parent.mkdir(parents=True)
        view.write_text(textwrap.dedent("""\
            package android.view;
            import java.util.LinkedHashMap;
            import java.util.Map;
            public class View {
                public static final int VISIBLE = 0, INVISIBLE = 4;
                public final Map<Runnable, Long> queue = new LinkedHashMap<>();
                public int visibility;
                public boolean owner, attached = true, failNext;
                public boolean postDelayed(Runnable task, long delay) { queue.put(task, delay); return true; }
                public boolean removeCallbacks(Runnable task) { queue.remove(task); return true; }
                public boolean isAttachedToWindow() { return attached; }
                public void setVisibility(int value) {
                    if (!owner) throw new IllegalStateException("Expected wmshell.main");
                    if (failNext) { failNext = false; throw new IllegalStateException("retry restore"); }
                    visibility = value;
                }
                public void flush() {
                    owner = true;
                    Runnable[] pending = queue.keySet().toArray(new Runnable[0]);
                    queue.clear();
                    for (Runnable task : pending) task.run();
                    owner = false;
                }
            }
        """))
        test = directory / "CaptionVisibilityTest.java"
        test.write_text(textwrap.dedent("""\
            import android.view.View;
            import local.gxr.curvature.CaptionVisibility;
            public final class CaptionVisibilityTest {
                private static void check(boolean value) { if (!value) throw new AssertionError(); }
                public static void main(String[] args) {
                    View view = new View();
                    CaptionVisibility caption = new CaptionVisibility(view);
                    caption.hide();
                    check(view.visibility == View.VISIBLE);
                    view.flush();
                    check(view.visibility == View.INVISIBLE && caption.getLastError() == null);
                    caption.hover(false); view.flush();
                    check(view.visibility == View.VISIBLE);
                    caption.hover(true);
                    check(view.queue.values().iterator().next() == 500L);
                    caption.hover(false); view.flush();
                    check(view.visibility == View.VISIBLE && view.queue.isEmpty());
                    caption.hover(true); view.flush();
                    check(view.visibility == View.INVISIBLE);
                    caption.close();
                    check(!caption.isRestored());
                    view.failNext = true; view.flush();
                    check(!caption.isRestored() && caption.getLastError() != null);
                    caption.close(); view.flush();
                    check(caption.isRestored() && view.visibility == View.VISIBLE);
                    check(caption.getLastError() == null && caption.owns(view));
                    caption.hover(true); view.flush();
                    check(view.visibility == View.VISIBLE);
                    View detached = new View();
                    CaptionVisibility old = new CaptionVisibility(detached);
                    old.hide(); detached.flush(); detached.attached = false;
                    old.close(); check(old.isRestored());
                    detached.attached = true; detached.flush();
                    check(detached.visibility == View.VISIBLE);
                    System.out.println("PASS: owner-thread hide/show, hover cancellation, restore acknowledgment and retry");
                }
            }
        """))
        classes = directory / "classes"
        subprocess.run([args.javac, "-Xlint:all", "-Werror", "-d", str(classes), str(view),
                        str(ROOT / "scripts/curvature/CaptionVisibility.java"), str(test)], check=True)
        subprocess.run([args.java, "-cp", str(classes), "CaptionVisibilityTest"], check=True)


if __name__ == "__main__":
    main()
