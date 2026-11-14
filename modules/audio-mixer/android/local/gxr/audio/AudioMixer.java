package local.gxr.audio;

import android.app.Dialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.media.AudioManager;
import android.media.AudioPlaybackConfiguration;
import android.media.VolumeShaper;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Switch;
import android.widget.TextView;
import java.lang.ref.WeakReference;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Native volume-panel extension. All listeners are Java, owned by the shared SystemUI runtime. */
public final class AudioMixer {
    private static final String TAG = "GxrAudioMixer";
    // Outside Android's 0–15 system envelopes and the normal sequential app IDs.
    private static final int SHAPER_ID = 0x475852;
    private final Context context;
    private final AudioManager audio;
    private final SharedPreferences preferences;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final MixerEngine engine = new MixerEngine();
    private final List<WeakReference<Panel>> panels = new ArrayList<>();
    private final Method clientUid;
    private final Method playerId;
    private final Method playerType;
    private final Method playerState;
    private final Method playerProxy;
    private final Method applyShape;
    private final Method setShapeId;
    private final Method setShapeOptions;
    private final Method terminate;
    private final Constructor<?> newOperation;
    private final Method buildOperation;
    private final Method replaceOperation;
    private final VolumeShaper.Configuration identity;
    private final VolumeShaper.Operation remove;
    private volatile boolean stopping;
    private volatile boolean stopped;
    private String error = "";
    private volatile int simultaneousSetting = -1;
    private final AudioManager.AudioPlaybackCallback callback = new AudioManager.AudioPlaybackCallback() {
        @Override public void onPlaybackConfigChanged(List<AudioPlaybackConfiguration> configs) {
            if (!stopping) refresh(configs);
        }
    };

    public AudioMixer(Context context) throws Exception {
        this.context = context;
        if (context.checkSelfPermission("android.permission.MODIFY_AUDIO_ROUTING") != PackageManager.PERMISSION_GRANTED) {
            throw new SecurityException("SystemUI lacks privileged playback access");
        }
        audio = (AudioManager) context.getSystemService(Context.AUDIO_SERVICE);
        preferences = context.getSharedPreferences("booinspace_audio_mixer", Context.MODE_PRIVATE);
        clientUid = AudioPlaybackConfiguration.class.getMethod("getClientUid");
        playerId = AudioPlaybackConfiguration.class.getMethod("getPlayerInterfaceId");
        playerType = AudioPlaybackConfiguration.class.getMethod("getPlayerType");
        playerState = AudioPlaybackConfiguration.class.getMethod("getPlayerState");
        playerProxy = AudioPlaybackConfiguration.class.getMethod("getPlayerProxy");
        applyShape = Class.forName("android.media.PlayerProxy").getMethod("applyVolumeShaper",
                VolumeShaper.Configuration.class, VolumeShaper.Operation.class);
        setShapeId = VolumeShaper.Configuration.Builder.class.getMethod("setId", int.class);
        setShapeOptions = VolumeShaper.Configuration.Builder.class.getMethod("setOptionFlags", int.class);
        Class<?> operationType = Class.forName("android.media.VolumeShaper$Operation$Builder");
        newOperation = operationType.getConstructor();
        buildOperation = operationType.getMethod("build");
        replaceOperation = operationType.getMethod("replace", int.class, boolean.class);
        terminate = operationType.getMethod("terminate");
        identity = VolumeShaper.Configuration.class.getConstructor(int.class).newInstance(SHAPER_ID);
        Object operation = newOperation.newInstance();
        terminate.invoke(operation);
        remove = (VolumeShaper.Operation) buildOperation.invoke(operation);
        Map<String, Integer> saved = new HashMap<>();
        for (Map.Entry<String, ?> entry : preferences.getAll().entrySet()) {
            if (entry.getKey().startsWith("app:") && entry.getValue() instanceof Integer) {
                int value = (Integer) entry.getValue();
                if (value >= 0 && value <= 100) saved.put(entry.getKey(), value);
            }
        }
        engine.load(saved);
    }

    public void start() {
        main.post(() -> {
            if (stopping) return;
            try {
                // A previous SystemUI process may have died while an app kept playing.
                for (MixerEngine.Player player : readPlayers(audio.getActivePlaybackConfigurations())) {
                    if (player.supported) player.clear();
                }
                engine.enable(preferences.getBoolean("enabled", true));
                audio.registerAudioPlaybackCallback(callback, main);
                refresh(audio.getActivePlaybackConfigurations());
                Log.i(TAG, "GXR_AUDIO_MIXER_READY");
            } catch (Exception failure) { failed(failure); }
        });
    }

    public void attach(Dialog dialog, boolean expanded, Object volumeDialog) {
        if (stopping || Looper.myLooper() != Looper.getMainLooper()) return;
        try {
            String name = expanded ? "volume_panel_dialog" : "volume_dialog_rows";
            int id = dialog.getContext().getResources().getIdentifier(name, "id", "com.android.systemui");
            View view = dialog.findViewById(id);
            if (!(view instanceof LinearLayout)) throw new IllegalStateException("Native volume layout changed: " + name);
            LinearLayout parent = (LinearLayout) view;
            for (int index = 0; index < parent.getChildCount(); index++) {
                if (parent.getChildAt(index).getTag() instanceof Panel) {
                    ((Panel) parent.getChildAt(index).getTag()).refresh();
                    return;
                }
            }
            Panel panel = new Panel(dialog, parent, expanded, volumeDialog);
            panels.add(new WeakReference<>(panel));
            panel.refresh();
        } catch (Exception failure) { failed(failure); }
    }

    private void failed(Exception failure) {
        error = "App mixer unavailable; stock volume controls remain available";
        Log.e(TAG, "GXR_AUDIO_MIXER_ERROR", failure);
        engine.enable(false);
        refreshPanels();
    }

    private void refresh(List<AudioPlaybackConfiguration> configs) {
        try {
            engine.update(readPlayers(configs));
            refreshPanels();
        } catch (Exception failure) { failed(failure); }
    }

    private List<MixerEngine.Player> readPlayers(List<AudioPlaybackConfiguration> configs) throws Exception {
        List<MixerEngine.Player> result = new ArrayList<>();
        for (AudioPlaybackConfiguration config : configs) {
            int uid = (Integer) clientUid.invoke(config);
            if (!MixerEngine.eligible(uid, config.getAudioAttributes().getUsage())) continue;
            String[] packages = context.getPackageManager().getPackagesForUid(uid);
            if (packages == null || packages.length == 0) continue;
            Arrays.sort(packages);
            String key = "app:" + (uid / 100000) + ":" + String.join(",", packages);
            StringBuilder label = new StringBuilder();
            for (String name : packages) {
                if (label.length() > 0) label.append(" / ");
                try {
                    ApplicationInfo info = context.getPackageManager().getApplicationInfo(name, 0);
                    label.append(context.getPackageManager().getApplicationLabel(info));
                } catch (PackageManager.NameNotFoundException missing) { label.append(name); }
            }
            if (packages.length > 1) label.append(" (shared audio UID)");
            Object proxy = playerProxy.invoke(config);
            int type = (Integer) playerType.invoke(config);
            result.add(new Player((Integer) playerId.invoke(config), key, label.toString(),
                    MixerEngine.playing((Integer) playerState.invoke(config)), proxy, type == 1 || type == 2));
        }
        return result;
    }

    private final class Player extends MixerEngine.Player {
        final Object proxy;
        Player(int id, String key, String label, boolean active, Object proxy, boolean supported) {
            super(id, key, label, active, proxy != null && supported);
            this.proxy = proxy;
        }
        @Override public void apply(int percent, boolean replace) throws Exception {
            float gain = MixerEngine.checkedPercent(percent) / 100f;
            VolumeShaper.Configuration.Builder shape = new VolumeShaper.Configuration.Builder()
                    .setCurve(new float[] {0, 1}, new float[] {gain, gain}).setDuration(1);
            setShapeId.invoke(shape, SHAPER_ID);
            setShapeOptions.invoke(shape, 2); // Clock time; independent of paused audio frame counters.
            Object operation = newOperation.newInstance();
            if (replace) replaceOperation.invoke(operation, SHAPER_ID, false);
            applyShape.invoke(proxy, shape.build(), buildOperation.invoke(operation));
        }
        @Override public void clear() throws Exception { applyShape.invoke(proxy, identity, remove); }
    }

    private void refreshPanels() {
        for (WeakReference<Panel> reference : new ArrayList<>(panels)) {
            Panel panel = reference.get();
            if (panel == null) panels.remove(reference); else panel.refresh();
        }
    }

    public void stop() {
        stopping = true;
        main.post(() -> {
            audio.unregisterAudioPlaybackCallback(callback);
            engine.enable(false);
            for (WeakReference<Panel> reference : panels) {
                Panel panel = reference.get();
                if (panel != null) panel.close();
            }
            panels.clear();
            stopped = engine.ownedCount() == 0;
            Log.i(TAG, "GXR_AUDIO_MIXER_STOPPED owned=" + engine.ownedCount());
        });
    }

    public boolean isStopped() { return stopped; }
    public String status() {
        return "enabled=" + engine.enabled() + " owned=" + engine.ownedCount() + " multiAudioSaved=" + simultaneousSetting + " error=" + error;
    }

    private final class Panel {
        final LinearLayout parent;
        final LinearLayout section;
        final LinearLayout rows;
        final ScrollView scroll;
        final Switch toggle;
        final Switch simultaneous;
        final TextView hint;
        final View outer;
        final int oldParentHeight;
        final int oldOuterHeight;
        final Object volumeDialog;
        final Context theme;
        boolean updating;
        boolean dragging;

        Panel(Dialog dialog, LinearLayout parent, boolean expanded, Object volumeDialog) {
            this.parent = parent;
            this.volumeDialog = volumeDialog;
            theme = parent.getContext();
            int outerId = theme.getResources().getIdentifier("volume_dialog_container", "id", "com.android.systemui");
            outer = expanded ? parent : dialog.findViewById(outerId);
            oldParentHeight = parent.getLayoutParams().height;
            oldOuterHeight = outer.getLayoutParams().height;
            section = new LinearLayout(theme);
            section.setTag(this);
            section.setOrientation(LinearLayout.VERTICAL);
            section.setPadding(dp(20), dp(8), dp(20), dp(8));
            toggle = new Switch(theme);
            toggle.setText("App mixer");
            toggle.setContentDescription("Enable individual app volume");
            section.addView(toggle, new LinearLayout.LayoutParams(-1, dp(48)));
            simultaneous = new Switch(theme);
            simultaneous.setText("Allow simultaneous media");
            simultaneous.setContentDescription("Allow multiple apps to play media; restart playback after enabling");
            section.addView(simultaneous, new LinearLayout.LayoutParams(-1, dp(48)));
            simultaneous.setOnCheckedChangeListener((button, checked) -> {
                if (updating || stopping) return;
                int previous = Settings.System.getInt(context.getContentResolver(), "multi_audio_focus_enabled", 0);
                try {
                    // AZJ2 applies the service flag without reliably persisting it.
                    if (!Settings.System.putInt(context.getContentResolver(), "multi_audio_focus_enabled", checked ? 1 : 0)
                            || Settings.System.getInt(context.getContentResolver(), "multi_audio_focus_enabled", -1) != (checked ? 1 : 0)) {
                        throw new IllegalStateException("Could not save multi-audio focus");
                    }
                    AudioManager.class.getMethod("setMultiAudioFocusEnabled", boolean.class).invoke(audio, checked);
                    Log.i(TAG, "Multi-audio focus saved and applied: " + checked);
                } catch (Exception failure) {
                    try {
                        if (!Settings.System.putInt(context.getContentResolver(), "multi_audio_focus_enabled", previous)) {
                            throw new IllegalStateException("Could not restore multi-audio setting");
                        }
                    } catch (Exception rollback) { failure.addSuppressed(rollback); }
                    Log.e(TAG, "Could not change native multi-audio focus", failure);
                    android.widget.Toast.makeText(theme, "Could not change simultaneous media", android.widget.Toast.LENGTH_LONG).show();
                }
                refreshPanels();
                touch();
            });
            hint = new TextView(theme);
            hint.setTextSize(12);
            section.addView(hint, new LinearLayout.LayoutParams(-1, dp(36)));
            scroll = new ScrollView(theme);
            rows = new LinearLayout(theme);
            rows.setOrientation(LinearLayout.VERTICAL);
            scroll.addView(rows, new ViewGroup.LayoutParams(-1, -2));
            section.addView(scroll, new LinearLayout.LayoutParams(-1, 0));
            toggle.setOnCheckedChangeListener((button, checked) -> {
                if (updating || stopping) return;
                preferences.edit().putBoolean("enabled", checked).apply();
                engine.enable(checked);
                refreshPanels();
                touch();
            });
            // The expanded panel's final child is its DND footer.
            parent.addView(section, expanded ? 1 : parent.getChildCount(), new LinearLayout.LayoutParams(-1, -2));
            section.setOnHoverListener((view, event) -> { touch(); return false; });
        }

        int dp(int value) { return Math.round(value * theme.getResources().getDisplayMetrics().density); }

        void touch() {
            if (volumeDialog == null) return;
            try {
                Method timeout = volumeDialog.getClass().getDeclaredMethod("rescheduleTimeoutH");
                timeout.setAccessible(true);
                timeout.invoke(volumeDialog);
            } catch (Exception failure) { Log.w(TAG, "Could not extend volume popup timeout", failure); }
        }

        void refresh() {
            if (dragging || stopping) return;
            updating = true;
            simultaneousSetting = Settings.System.getInt(context.getContentResolver(), "multi_audio_focus_enabled", 0);
            simultaneous.setChecked(simultaneousSetting != 0);
            toggle.setChecked(engine.enabled());
            toggle.setEnabled(error.isEmpty());
            Map<String, List<MixerEngine.Player>> groups = new LinkedHashMap<>();
            for (MixerEngine.Player player : engine.players()) {
                if (!player.active) continue;
                if (!groups.containsKey(player.key)) groups.put(player.key, new ArrayList<>());
                groups.get(player.key).add(player);
            }
            rows.removeAllViews();
            hint.setText(!error.isEmpty() ? error : !engine.enabled() ? "App levels bypassed; master volume is unchanged."
                    : groups.isEmpty() ? "Play audio in an app to adjust it here."
                    : "App level × existing app volume × master volume");
            if (engine.enabled()) for (Map.Entry<String, List<MixerEngine.Player>> group : groups.entrySet()) {
                addRow(group.getKey(), group.getValue());
            }
            if (engine.enabled() && !groups.isEmpty()) {
                Button reset = new Button(theme);
                reset.setText("Reset app volumes");
                reset.setOnClickListener(view -> {
                    if (stopping) return;
                    SharedPreferences.Editor editor = preferences.edit();
                    for (String key : preferences.getAll().keySet()) if (key.startsWith("app:")) editor.remove(key);
                    editor.apply();
                    engine.reset();
                    refreshPanels();
                    touch();
                });
                rows.addView(reset, new LinearLayout.LayoutParams(-1, dp(48)));
            }
            int contentHeight = engine.enabled() && !groups.isEmpty() ? Math.min(3 * 80, groups.size() * 80 + 48) : 0;
            scroll.getLayoutParams().height = dp(contentHeight);
            scroll.requestLayout();
            int extra = dp(148 + contentHeight);
            parent.getLayoutParams().height = oldParentHeight > 0 ? oldParentHeight + extra : -2;
            if (outer != parent) outer.getLayoutParams().height = oldOuterHeight > 0 ? oldOuterHeight + extra : -2;
            parent.requestLayout();
            outer.requestLayout();
            updating = false;
        }

        void addRow(String key, List<MixerEngine.Player> players) {
            boolean supported = true;
            for (MixerEngine.Player player : players) supported &= player.supported;
            final TextView label = new TextView(theme);
            label.setSingleLine(true);
            label.setEllipsize(android.text.TextUtils.TruncateAt.END);
            String name = players.get(0).label;
            String problem = engine.failures().get(key);
            label.setText(name + (supported ? " · " + engine.level(key) + "%" : " · unsupported audio player"));
            rows.addView(label, new LinearLayout.LayoutParams(-1, dp(28)));
            SeekBar slider = new SeekBar(theme);
            slider.setMax(100);
            slider.setProgress(engine.level(key));
            slider.setEnabled(supported && problem == null);
            slider.setContentDescription(name + " app volume percent");
            if (problem != null) label.setText(name + " · " + problem);
            slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
                long lastApply;
                void apply(int value, boolean save) {
                    if (stopping) return;
                    engine.set(key, value);
                    if (save) preferences.edit().putInt(key, value).apply();
                }
                @Override public void onStartTrackingTouch(SeekBar bar) { dragging = true; touch(); }
                @Override public void onProgressChanged(SeekBar bar, int value, boolean user) {
                    if (!user || stopping) return;
                    label.setText(name + " · " + value + "%");
                    long now = SystemClock.uptimeMillis();
                    if (!dragging || now - lastApply >= 50) {
                        apply(value, !dragging);
                        lastApply = now;
                    }
                    touch();
                }
                @Override public void onStopTrackingTouch(SeekBar bar) {
                    apply(bar.getProgress(), true);
                    dragging = false;
                    refreshPanels();
                    touch();
                }
            });
            rows.addView(slider, new LinearLayout.LayoutParams(-1, dp(52)));
        }

        void close() {
            toggle.setOnCheckedChangeListener(null);
            parent.removeView(section);
            parent.getLayoutParams().height = oldParentHeight;
            if (outer != parent) outer.getLayoutParams().height = oldOuterHeight;
            parent.requestLayout();
            outer.requestLayout();
        }
    }
}
