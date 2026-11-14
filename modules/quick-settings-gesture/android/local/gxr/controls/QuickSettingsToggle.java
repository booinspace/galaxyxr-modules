package local.gxr.controls;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.Log;
import android.view.View;

/** Dispatches the stock Quick Settings action on its UI thread without a JavaScript listener. */
public final class QuickSettingsToggle {
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Object token = new Object();
    private final View.OnClickListener action;
    private final PowerManager power;
    private volatile boolean enabled;
    private volatile boolean closed;
    private volatile long generation;
    private volatile int requests;
    private volatile String error = "";

    public QuickSettingsToggle(Context context, View.OnClickListener action) {
        if (action == null) throw new IllegalArgumentException("Missing stock Quick Settings action");
        this.action = action;
        power = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
        if (power == null) throw new IllegalStateException("Power service unavailable");
    }

    public synchronized void setEnabled(boolean value) {
        cancel();
        enabled = value && !closed;
        if (enabled) error = "";
    }

    public synchronized void cancel() {
        generation++;
        main.removeCallbacksAndMessages(token);
    }

    public synchronized void request() {
        if (!enabled || closed) return;
        final long ticket = generation;
        final long requestedAt = SystemClock.uptimeMillis();
        boolean posted = main.postAtTime(() -> {
            synchronized (QuickSettingsToggle.this) {
                if (closed || !enabled || ticket != generation
                        || SystemClock.uptimeMillis() - requestedAt > 250) return;
            }
            // The native action can enter the compositor; never hold the input-side monitor across it.
            try {
                if (!power.isInteractive()) return;
                action.onClick(null);
                requests++;
                Log.i("GxrQuickSettings", "Native Quick Settings action dispatched");
            } catch (RuntimeException failure) {
                error = failure.toString();
                enabled = false;
                Log.e("GxrQuickSettings", "Native Quick Settings action failed", failure);
            }
        }, token, requestedAt);
        if (!posted) {
            enabled = false;
            error = "Quick Settings looper is unavailable";
        }
    }

    public synchronized void close() {
        closed = true;
        enabled = false;
        cancel();
    }

    public int getRequests() { return requests; }
    public String getError() { return error; }
}
