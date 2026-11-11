/** Read-only signature check; no CPM node, audio callback or property setter is invoked. */
public final class PortApiProbe {
    public static void main(String[] args) throws Exception {
        Class<?> node = Class.forName("android.graphics.CPM$Node");
        Class<?> updates = Class.forName("android.graphics.CPM$NodeUpdates");
        Class.forName("android.graphics.CPM").getMethod("getPassthroughNode");
        updates.getConstructor();
        updates.getMethod("setAlpha", node, float.class);
        updates.getMethod("setZ", node, int.class);
        updates.getMethod("setVisible", node, boolean.class);
        updates.getMethod("apply");
        Class<?> dispatcher = Class.forName("android.media.IRecordingConfigDispatcher");
        Class<?> audio = Class.forName("android.media.IAudioService");
        audio.getMethod("registerRecordingCallback", dispatcher);
        audio.getMethod("getActiveRecordingConfigurations");
        Class<?> recording = Class.forName("android.media.AudioRecordingConfiguration");
        recording.getMethod("getClientAudioSource");
        recording.getMethod("getClientPackageName");
        recording.getMethod("isClientSilenced");
        Class<?> tasks = Class.forName("android.app.IActivityTaskManager");
        tasks.getMethod("getFocusedRootTaskInfo");
        tasks.getMethod("registerTaskStackListener", Class.forName("android.app.ITaskStackListener"));
        Class.forName("android.app.WindowConfiguration").getMethod("getComputedXrDesktopMode");
        java.lang.reflect.Field fullSpace = Class.forName("android.app.WindowConfiguration")
                .getDeclaredField("XR_COMPUTED_DESKTOP_MODE_FULL_SPACE_UNMANAGED");
        fullSpace.setAccessible(true);
        if (fullSpace.getInt(null) != 2) throw new IllegalStateException("Full-space enum changed");
        System.out.println("PASS: required CPM, recording and XR-focus signatures exist");
    }
}
