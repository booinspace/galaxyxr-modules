package local.gxr.pins;

import android.app.ActivityManager.RunningTaskInfo;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.Path;
import android.graphics.drawable.ShapeDrawable;
import android.graphics.drawable.shapes.PathShape;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.Toast;
import local.gxr.rotation.WindowFeatures;

/** Adds a native pin button to the existing caption menu without granting SystemUI root. */
public final class PinMenu implements AutoCloseable, View.OnClickListener {
    private static PinMenu pending;
    private static long heartbeat = -1;
    private static String supervisorToken = "";
    private final Button button;
    private final ViewGroup parent;
    private final Handler owner = new Handler(Looper.myLooper());
    private final int taskId;
    private final String packageName;
    private PinRequest request;
    private boolean emitted;
    private boolean closed;
    private long confirmAt = -1;
    private final Runnable expired = () -> finish(false);

    public static PinMenu attach(View root, Object task) throws Exception {
        RunningTaskInfo info = (RunningTaskInfo) task;
        int mode = info.getClass().getField("xrDesktopMode").getInt(info);
        if (info.getClass().getField("userId").getInt(info) != 0 || info.baseActivity == null ||
                info.topActivity == null || !info.baseActivity.getPackageName().equals(info.topActivity.getPackageName())) return null;
        String pkg = info.baseActivity.getPackageName();
        ApplicationInfo app;
        try { app = root.getContext().getPackageManager().getApplicationInfo(pkg, 0); }
        catch (PackageManager.NameNotFoundException | SecurityException unavailable) { return null; }
        if (!PinCli.allowedApplication(app, pkg)) return null;
        boolean pinned = mode == 4 && info.baseIntent != null && info.baseIntent.hasCategory(PinCli.MARKER);
        if (mode != 1 && !pinned) return null;
        return new PinMenu(root, info.taskId, pkg, pinned);
    }

    private PinMenu(View root, int taskId, String packageName, boolean pinned) {
        this.taskId = taskId;
        this.packageName = packageName;
        int listId = root.getResources().getIdentifier("more_actions_list", "id", "com.android.systemui");
        int templateId = root.getResources().getIdentifier("app_info_button", "id", "com.android.systemui");
        View list = root.findViewById(listId), templateView = root.findViewById(templateId);
        if (!(list instanceof ViewGroup) || !(templateView instanceof Button)) {
            throw new IllegalStateException("Stock caption menu layout changed");
        }
        parent = (ViewGroup) list;
        Button template = (Button) templateView;
        button = new Button(root.getContext());
        button.setAllCaps(false);
        button.setTypeface(template.getTypeface());
        button.setTextColor(template.getTextColors());
        button.setTextSize(android.util.TypedValue.COMPLEX_UNIT_PX, template.getTextSize());
        button.setPadding(template.getPaddingLeft(), template.getPaddingTop(), template.getPaddingRight(), template.getPaddingBottom());
        if (template.getBackground() != null && template.getBackground().getConstantState() != null) {
            button.setBackground(template.getBackground().getConstantState().newDrawable().mutate());
        }
        Path path = new Path();
        path.moveTo(8, 3); path.lineTo(16, 3); path.lineTo(16, 5); path.lineTo(14, 5);
        path.lineTo(14, 11); path.lineTo(18, 15); path.lineTo(18, 17); path.lineTo(13, 17);
        path.lineTo(12, 23); path.lineTo(11, 17); path.lineTo(6, 17); path.lineTo(6, 15);
        path.lineTo(10, 11); path.lineTo(10, 5); path.lineTo(8, 5); path.close();
        ShapeDrawable icon = new ShapeDrawable(new PathShape(path, 24, 24));
        icon.setTintList(template.getTextColors());
        icon.setBounds(0, 0, dp(24), dp(24));
        button.setCompoundDrawablesRelative(icon, null, null, null);
        button.setCompoundDrawablePadding(dp(12));
        button.setText(pinned ? "Pinned over immersive apps" : "Pin app");
        button.setContentDescription(pinned ? "App is pinned over immersive apps" : "Pin this app over immersive apps");
        button.setEnabled(!pinned);
        button.setOnClickListener(this);
        try {
            parent.addView(button, 0, new ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, getRequiredHeight()));
        } catch (RuntimeException failure) {
            button.setOnClickListener(null);
            try { parent.removeView(button); }
            catch (RuntimeException cleanup) { failure.addSuppressed(cleanup); }
            throw failure;
        }
    }

    private int dp(int value) { return Math.round(value * button.getResources().getDisplayMetrics().density); }
    public int getRequiredHeight() { return dp(56); }
    public static synchronized void pulse() { heartbeat = SystemClock.uptimeMillis(); }
    public static synchronized void setToken(String value) {
        if (!value.matches("[0-9a-f]{32}")) throw new IllegalArgumentException("Invalid supervisor token");
        if (!supervisorToken.equals(value)) shutdown();
        supervisorToken = value;
    }

    @Override public void onClick(View ignored) {
        long now = SystemClock.uptimeMillis();
        synchronized (PinMenu.class) {
            if (closed || supervisorToken.isEmpty() || heartbeat < 0 || now < heartbeat ||
                    now - heartbeat > WindowFeatures.SUPERVISOR_LEASE_MS) {
                toast("Window Controls is not running"); return;
            }
            if (pending != null) { toast("Another pin operation is running"); return; }
            if (!PinRequest.confirmed(now, confirmAt)) {
                confirmAt = now;
                button.setText("Reopen and pin");
                button.setContentDescription("Reopen and pin this app. Save any unsaved changes before pressing again.");
                toast("Pinning reopens this window. Save changes, then tap Reopen and pin.");
                return;
            }
            request = new PinRequest(now, taskId, packageName);
            pending = this;
            emitted = false;
            button.setEnabled(false);
            button.setText("Pinning…");
            owner.postDelayed(expired, 30000);
        }
    }

    public static synchronized String pollRequest() {
        if (pending == null || pending.emitted) return "";
        pending.emitted = true;
        return supervisorToken + " " + pending.request.toWire();
    }

    public static synchronized void complete(long id, boolean success) {
        if (pending == null || pending.request.issuedAt != id) return;
        PinMenu menu = pending;
        menu.owner.post(() -> menu.finish(success));
    }

    private void finish(boolean success) {
        synchronized (PinMenu.class) {
            if (pending != this) return;
            pending = null;
            owner.removeCallbacks(expired);
            if (!closed) {
                button.setText(success ? "Pinned" : "Pin app");
                button.setContentDescription(success ? "App is pinned over immersive apps" : "Pin this app over immersive apps");
                button.setEnabled(!success);
                confirmAt = -1;
            }
        }
        toast(success ? "App pinned over immersive apps" : "Pin failed. Export Window Controls logs for details.");
    }

    public static synchronized void shutdown() {
        heartbeat = -1;
        supervisorToken = "";
        if (pending != null) {
            PinMenu menu = pending;
            pending = null;
            menu.owner.removeCallbacks(menu.expired);
        }
    }

    private void toast(String text) { Toast.makeText(button.getContext(), text, Toast.LENGTH_LONG).show(); }
    @Override public void close() {
        if (closed) return;
        button.setOnClickListener(null);
        parent.removeView(button);
        closed = true;
    }
}
