package local.gxr.curvature;

import android.view.View;
import java.lang.ref.WeakReference;

/** Keeps delayed caption changes on the view owner, which can be wmshell.main. */
public final class CaptionVisibility implements AutoCloseable {
    private final WeakReference<View> view;
    private volatile boolean closing;
    private volatile boolean restored;
    private volatile String error;
    private final Runnable hide = () -> apply(View.INVISIBLE, false);
    private final Runnable show = () -> apply(View.VISIBLE, false);
    private final Runnable restore = () -> apply(View.VISIBLE, true);

    public CaptionVisibility(View target) {
        if (target == null) throw new IllegalArgumentException("Missing caption view");
        view = new WeakReference<>(target);
    }

    private void apply(int visibility, boolean cleanup) {
        if (closing && !cleanup) return;
        try {
            View target = view.get();
            if (target != null) target.setVisibility(visibility);
            if (cleanup) restored = true;
            error = null;
        } catch (RuntimeException failure) { error = failure.toString(); }
    }

    private void post(Runnable task, long delay) {
        View target = view.get();
        if (target == null) return;
        target.removeCallbacks(hide);
        target.removeCallbacks(show);
        if (!target.postDelayed(task, delay)) throw new IllegalStateException("Caption owner stopped");
    }

    public void hide() { if (!closing) post(hide, 0); }

    public void hover(boolean exiting) { if (!closing) post(exiting ? hide : show, exiting ? 500 : 0); }

    public boolean owns(View candidate) { return view.get() == candidate; }

    public boolean isCollected() { return view.get() == null; }

    public String getLastError() { return error; }

    public boolean isRestored() { return restored || view.get() == null; }

    @Override public void close() {
        closing = true;
        View target = view.get();
        if (target == null) { restored = true; return; }
        if (restored) return;
        // Detached views have no live surface; retain a queued restore for reattachment.
        boolean detached = !target.isAttachedToWindow();
        post(restore, 0);
        if (detached) restored = true;
    }
}
