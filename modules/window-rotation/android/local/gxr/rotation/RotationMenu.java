package local.gxr.rotation;

import android.content.Context;
import android.util.TypedValue;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;

/** Native Android listeners remain valid when Frida detaches. */
public final class RotationMenu implements View.OnAttachStateChangeListener, AutoCloseable {
    final View root;
    volatile boolean closed;
    private final RotationController controller;
    private final RotationController.Session session;
    private final Object menu;
    private final Object pill;
    private final ViewGroup parent;
    private final LinearLayout controls;
    private final SeekBar[] bars = new SeekBar[3];
    private final TextView[] labels = new TextView[3];
    private final Button reset;
    private final int oldHeight;
    private final boolean sharedHost;
    private static final String[] AXES = {"Pitch", "Yaw", "Roll"};

    RotationMenu(RotationController controller, RotationController.Session session,
            Object menu, View root, boolean sharedHost) throws Exception {
        this.controller = controller;
        this.session = session;
        this.menu = menu;
        this.root = root;
        this.sharedHost = sharedHost;
        pill = RotationController.field(menu, "moreActionsPill");
        oldHeight = (Integer) RotationController.call(pill, "getHeight");
        int listId = root.getResources().getIdentifier("more_actions_list", "id", "com.android.systemui");
        int templateId = root.getResources().getIdentifier("app_info_button", "id", "com.android.systemui");
        View list = root.findViewById(listId);
        View templateView = root.findViewById(templateId);
        if (!(list instanceof ViewGroup) || !(templateView instanceof Button)) {
            throw new IllegalStateException("Stock caption menu layout changed");
        }
        parent = (ViewGroup) list;
        Button template = (Button) templateView;
        Context context = root.getContext();
        controls = new LinearLayout(context);
        controls.setOrientation(LinearLayout.VERTICAL);
        for (int axis = 0; axis < 3; axis++) {
            final int index = axis;
            TextView label = new TextView(context);
            labels[axis] = label;
            label.setTextColor(template.getTextColors());
            label.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
            label.setPadding(dp(16), 0, dp(16), 0);
            controls.addView(label, new LinearLayout.LayoutParams(-1, dp(24)));
            SeekBar bar = new SeekBar(context);
            bars[axis] = bar;
            bar.setMax(360);
            bar.setProgress(session.angles[axis] + 180);
            bar.setPadding(dp(24), 0, dp(24), 0);
            bar.setContentDescription(AXES[axis] + " window rotation in degrees; applies on release");
            bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
                private boolean tracking;
                @Override public void onStartTrackingTouch(SeekBar view) { tracking = true; }
                @Override public void onProgressChanged(SeekBar view, int progress, boolean fromUser) {
                    labels[index].setText(AXES[index] + ": " + (progress - 180) + "°");
                    if (fromUser && !tracking) apply(index, progress - 180);
                }
                @Override public void onStopTrackingTouch(SeekBar view) {
                    tracking = false;
                    apply(index, view.getProgress() - 180);
                }
            });
            label.setText(AXES[axis] + ": " + session.angles[axis] + "°");
            controls.addView(bar, new LinearLayout.LayoutParams(-1, dp(48)));
        }
        reset = new Button(context);
        reset.setText("Reset rotation");
        reset.setTypeface(template.getTypeface());
        reset.setTextColor(template.getTextColors());
        reset.setOnClickListener(view -> {
            if (closed) return;
            try {
                session.reset();
                for (SeekBar bar : bars) bar.setProgress(180);
            } catch (Exception failure) { controller.fail(failure); }
        });
        controls.addView(reset, new LinearLayout.LayoutParams(-1, dp(56)));
        try {
            int height = oldHeight + dp(272);
            int width = (Integer) RotationController.field(menu, "menuWidth");
            if (width <= 0 || height <= 0 || width > 16384 || height > 16384) {
                throw new IllegalStateException("Invalid menu surface bounds");
            }
            parent.addView(controls, new ViewGroup.LayoutParams(-1, dp(272)));
            if (!sharedHost) {
                Object window = RotationController.field(pill, "window");
                Object host = RotationController.field(window, "mWindowViewHost");
                Object surface = RotationController.field(window, "mWindowSurface");
                RotationController.call(pill, "setHeight", new Class<?>[] {int.class}, height);
                RotationController.call(host, "relayout", new Class<?>[] {int.class, int.class}, width, height);
                Class<?> transactionType = Class.forName("android.view.SurfaceControl$Transaction");
                Object transaction = transactionType.getConstructor().newInstance();
                try {
                    RotationController.call(transaction, "setWindowCrop", new Class<?>[] {
                        Class.forName("android.view.SurfaceControl"), int.class, int.class}, surface, width, height);
                    RotationController.call(menu, "relayout", new Class<?>[] {transactionType}, transaction);
                    RotationController.call(transaction, "apply");
                } finally { RotationController.call(transaction, "close"); }
            }
            root.addOnAttachStateChangeListener(this);
        } catch (Exception failure) {
            try { close(true); } catch (Exception cleanup) { failure.addSuppressed(cleanup); }
            throw failure;
        }
    }

    private int dp(int value) {
        return Math.round(value * root.getResources().getDisplayMetrics().density);
    }

    /** Added to the Curvature menu's single backing-surface resize. */
    public int getRequiredHeight() { return dp(272); }

    @Override public void close() throws Exception { close(false); }

    private void apply(int axis, int degrees) {
        if (closed) return;
        try { session.set(axis, degrees); }
        catch (Exception failure) { controller.fail(failure); }
    }

    void close(boolean dismiss) throws Exception {
        if (closed) return;
        root.removeOnAttachStateChangeListener(this);
        for (SeekBar bar : bars) bar.setOnSeekBarChangeListener(null);
        reset.setOnClickListener(null);
        parent.removeView(controls);
        if (!sharedHost) RotationController.call(pill, "setHeight", new Class<?>[] {int.class}, oldHeight);
        if (!sharedHost && dismiss && RotationController.root(menu) == root && root.isAttachedToWindow()) {
            // The enlarged host and its crop disappear together with the stock menu.
            RotationController.call(menu, "close");
        }
        closed = true;
    }

    @Override public void onViewAttachedToWindow(View view) { }
    @Override public void onViewDetachedFromWindow(View view) {
        try { close(false); }
        catch (Exception failure) { controller.fail(failure); }
    }
}
