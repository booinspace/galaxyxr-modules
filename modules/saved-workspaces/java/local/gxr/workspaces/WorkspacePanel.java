package local.gxr.workspaces;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.File;
import java.util.ArrayList;
import java.util.List;

/** Native views inside stock OverviewView; the original task list keeps its binder and constraints. */
final class WorkspacePanel implements AutoCloseable {
    final Object element;
    private final Context context;
    private final WorkspaceController controller;
    private final ViewGroup root, original;
    private final LinearLayout column, strip, editor, setup;
    private final ScrollView viewport;
    private final TextView status;
    private final List<View> children = new ArrayList<>();
    private final List<ViewGroup.LayoutParams> positions = new ArrayList<>();
    private final Button save, add, stopWaiting;
    private final int foreground, surface, accent;
    private String rendered = "";
    private boolean closed;
    private final View.OnAttachStateChangeListener lifetime = new View.OnAttachStateChangeListener() {
        @Override public void onViewAttachedToWindow(View view) {}
        @Override public void onViewDetachedFromWindow(View view) { controller.detach(WorkspacePanel.this); }
    };
    WorkspacePanel(Context context, Object element, WorkspaceController controller) throws Exception {
        this.context = context; this.element = element; this.controller = controller;
        Object xrView = AndroidAccess.get(element, "getView");
        View content = (View)AndroidAccess.get(xrView, "getContentView");
        if (!(content instanceof ViewGroup) || !content.getClass().getName().endsWith("OverviewView")) throw new IllegalStateException("Unexpected AZJ2 Recents view");
        root = (ViewGroup)content;
        foreground = color(android.R.attr.textColorPrimary, Color.WHITE);
        surface = color(android.R.attr.colorBackgroundFloating, 0xff28292d);
        accent = color(android.R.attr.colorAccent, 0xffb8c7ff);
        original = (ViewGroup)context.getClassLoader().loadClass("androidx.constraintlayout.widget.ConstraintLayout").getConstructor(Context.class).newInstance(context);
        column = new LinearLayout(context); column.setOrientation(LinearLayout.VERTICAL); column.setGravity(Gravity.CENTER_HORIZONTAL);
        LinearLayout controls = new LinearLayout(context); controls.setOrientation(LinearLayout.VERTICAL);
        controls.setPadding(dp(16), dp(12), dp(16), dp(20));
        int suggestionsId = root.getResources().getIdentifier("overview_app_suggestions", "id", "com.android.systemui");
        View suggestions = root.findViewById(suggestionsId);
        // AZJ2 gives its centered app-suggestions row a fixed width inside the wider Recents surface.
        int contentWidth = suggestions == null ? dp(720) : suggestions.getLayoutParams().width;
        if (contentWidth <= 0) throw new IllegalStateException("Native Recents content width is unavailable");
        column.addView(controls, new LinearLayout.LayoutParams(contentWidth, -2));
        viewport = new ScrollView(context); viewport.setFillViewport(true); viewport.setClipToPadding(false);
        viewport.addView(column, new ViewGroup.LayoutParams(-1, -2));
        LinearLayout header = new LinearLayout(context); header.setGravity(Gravity.CENTER_VERTICAL);
        TextView title = label("Workspaces", 20); title.setTypeface(null, Typeface.BOLD);
        header.addView(title, new LinearLayout.LayoutParams(0, dp(44), 1));
        save = button("Save layout", controller::saveCurrent); header.addView(save);
        add = button("New", () -> edit(null)); header.addView(add);
        stopWaiting = button("Stop waiting", controller::stopWaiting);
        stopWaiting.setOnClickListener(v -> controller.stopWaiting());
        stopWaiting.setVisibility(View.GONE); header.addView(stopWaiting);
        controls.addView(header);
        status = label("", 13); status.setPadding(0, dp(4), 0, dp(12));
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE); controls.addView(status);
        setup = new LinearLayout(context); setup.setOrientation(LinearLayout.VERTICAL); setup.setPadding(0, dp(8), 0, dp(12));
        setup.addView(label("Switching closes windows outside the chosen workspace and pauses their media. Unsaved app work can be lost. Apps reopen at their normal launch screen. Layouts and previews stay on this headset.", 14));
        setup.addView(button("Enable workspace switching", controller::acknowledge)); controls.addView(setup);
        HorizontalScrollView scrolling = new HorizontalScrollView(context); scrolling.setHorizontalScrollBarEnabled(false); scrolling.setFillViewport(true);
        strip = new LinearLayout(context); strip.setOrientation(LinearLayout.HORIZONTAL); strip.setPadding(0, 0, 0, dp(8)); strip.setGravity(Gravity.CENTER_HORIZONTAL);
        scrolling.addView(strip); controls.addView(scrolling, new LinearLayout.LayoutParams(-1, dp(132)));
        editor = new LinearLayout(context); editor.setGravity(Gravity.CENTER_VERTICAL); editor.setPadding(0, dp(8), 0, dp(8));
        editor.setVisibility(View.GONE); controls.addView(editor);
        column.addView(original, new LinearLayout.LayoutParams(-1, -2));
        for (int i = 0; i < root.getChildCount(); i++) { View child = root.getChildAt(i); children.add(child); positions.add(child.getLayoutParams()); }
        // All original IDs and ConstraintLayout parameters stay together in their original order.
        try {
            root.removeAllViews();
            for (int i = 0; i < children.size(); i++) original.addView(children.get(i), positions.get(i));
            root.addView(viewport, new ViewGroup.LayoutParams(-1, -1));
            strip.setOnClickListener(v -> { /* Keep Recents open while choosing a workspace. */ });
            header.setOnClickListener(v -> {}); setup.setOnClickListener(v -> {}); editor.setOnClickListener(v -> {});
            root.addOnAttachStateChangeListener(lifetime);
            refresh();
        } catch (Exception error) { close(); throw error; }
    }
    private int dp(int value) { return Math.round(value * context.getResources().getDisplayMetrics().density); }
    private int color(int attribute, int fallback) {
        android.content.res.TypedArray values = context.obtainStyledAttributes(new int[]{attribute});
        try { return values.getColor(0, fallback); } finally { values.recycle(); }
    }
    private TextView label(String text, int size) {
        TextView view = new TextView(context); view.setText(text); view.setTextSize(size); view.setTextColor(foreground); view.setGravity(Gravity.CENTER_VERTICAL); return view;
    }
    private Button button(String text, Runnable action) {
        Button button = new Button(context); button.setText(text); button.setAllCaps(false); button.setMinHeight(dp(40));
        button.setContentDescription(text); button.setOnClickListener(v -> { if (!controller.busy()) action.run(); }); return button;
    }
    void refresh() {
        if (closed) return;
        WorkspaceStore.Index index = controller.index(); boolean busy = controller.busy();
        stopWaiting.setVisibility(busy && !index.pending.isEmpty() ? View.VISIBLE : View.GONE);
        status.setText(index.pending.isEmpty() || busy ? controller.text() : "Opening " + index.get(index.pending).name
                + " is unfinished. Apps were kept open. Select it to retry, or choose another workspace. " + controller.text());
        save.setEnabled(!busy && controller.bound()); add.setEnabled(!busy && index.acknowledged && index.workspaces.size() < Workspace.MAX_WORKSPACES);
        setup.setVisibility(index.acknowledged ? View.GONE : View.VISIBLE);
        StringBuilder key = new StringBuilder(index.active).append(index.pending).append(busy).append(index.acknowledged);
        for (Workspace workspace : index.workspaces) key.append(workspace.id).append(workspace.name).append(workspace.windows.size()).append(controller.preview(workspace.id).lastModified());
        if (rendered.equals(key.toString())) return; rendered = key.toString();
        strip.removeAllViews();
        for (Workspace workspace : index.workspaces) {
            boolean active = (index.pending.isEmpty() ? index.active : index.pending).equals(workspace.id);
            LinearLayout card = new LinearLayout(context); card.setOrientation(LinearLayout.VERTICAL); card.setPadding(dp(5), dp(5), dp(5), dp(5));
            GradientDrawable shape = new GradientDrawable(); shape.setColor(surface); shape.setCornerRadius(dp(16)); if (active) shape.setStroke(dp(2), accent);
            card.setBackground(new RippleDrawable(ColorStateList.valueOf(0x44ffffff), shape, null));
            File preview = controller.preview(workspace.id);
            ImageView image = new ImageView(context); image.setScaleType(ImageView.ScaleType.CENTER_CROP);
            if (preview.isFile() && preview.length() <= 512 * 1024 && !java.nio.file.Files.isSymbolicLink(preview.toPath())) image.setImageBitmap(BitmapFactory.decodeFile(preview.getPath()));
            else image.setImageResource(android.R.drawable.ic_menu_gallery);
            image.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            card.addView(image, new LinearLayout.LayoutParams(-1, dp(72)));
            TextView name = label(workspace.name + (active ? index.pending.isEmpty() ? " · current" : busy ? " · opening" : " · unfinished" : ""), 14); name.setSingleLine(true); name.setEllipsize(android.text.TextUtils.TruncateAt.END);
            card.addView(name, new LinearLayout.LayoutParams(-1, dp(26)));
            TextView count = label(workspace.windows.isEmpty() ? "Empty workspace" : workspace.windows.size() + (workspace.windows.size() == 1 ? " app" : " apps"), 11); card.addView(count);
            card.setContentDescription("Open " + workspace.name + ", " + workspace.windows.size() + " apps. Hold to rename or delete.");
            card.setEnabled(!busy && index.acknowledged); card.setFocusable(true); card.setClickable(true);
            card.setOnClickListener(v -> { if (!controller.busy() && controller.index().acknowledged) controller.select(workspace, element); });
            card.setOnLongClickListener(v -> { if (!controller.busy()) edit(workspace); return true; });
            LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(dp(180), -1); layout.setMargins(dp(4), 0, dp(4), 0); strip.addView(card, layout);
        }
    }
    private void edit(Workspace workspace) {
        editor.removeAllViews(); editor.setVisibility(View.VISIBLE);
        EditText name = new EditText(context); name.setSingleLine(true); name.setTextColor(foreground); name.setHintTextColor(foreground & 0x99ffffff);
        name.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(40)});
        name.setHint("Workspace name"); name.setContentDescription("Workspace name"); if (workspace != null) name.setText(workspace.name);
        editor.addView(name, new LinearLayout.LayoutParams(0, dp(48), 1));
        editor.addView(button(workspace == null ? "Create" : "Rename", () -> {
            if (workspace == null) controller.create(name.getText().toString(), element); else controller.rename(workspace.id, name.getText().toString()); editor.setVisibility(View.GONE);
        }));
        if (workspace != null && !workspace.id.equals(controller.index().active)) editor.addView(button("Delete…", () -> {
            editor.removeAllViews(); editor.addView(label("Delete “" + workspace.name + "” and its saved layout?", 14));
            editor.addView(button("Delete workspace", () -> { controller.remove(workspace.id); editor.setVisibility(View.GONE); }));
            editor.addView(button("Cancel", () -> editor.setVisibility(View.GONE)));
        }));
        editor.addView(button("Cancel", () -> editor.setVisibility(View.GONE)));
    }
    boolean attached() { return !closed && viewport.getParent() == root; }
    @Override public void close() {
        if (closed) return; closed = true;
        root.removeOnAttachStateChangeListener(lifetime);
        root.removeView(viewport); original.removeAllViews();
        for (int i = 0; i < children.size(); i++) if (children.get(i).getParent() == null) root.addView(children.get(i), positions.get(i));
        children.clear(); positions.clear();
    }
}
