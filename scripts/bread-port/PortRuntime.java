package com.gxr.port;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.Properties;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** Cooperative root-daemon lifetime and a journal that never crosses a full boot. */
public final class PortRuntime {
    public interface Cleanup { void run() throws Exception; }
    public final File module;
    public final File runtime;
    public volatile boolean stopping;
    private final AtomicBoolean cleaned = new AtomicBoolean();
    private Cleanup cleanup;

    public PortRuntime(String directory) throws IOException {
        module = new File(directory).getCanonicalFile();
        String state = System.getenv("GXR_PORT_STATE");
        if (state == null || !state.startsWith("/dev/gxr_")) throw new IOException("Missing runtime directory");
        runtime = new File(state);
    }

    public static String boot() throws IOException {
        return new String(Files.readAllBytes(new File("/proc/sys/kernel/random/boot_id").toPath()),
                StandardCharsets.US_ASCII).trim();
    }

    public static void write(File file, String value) throws IOException {
        File temporary = new File(file.getPath() + ".new");
        try (FileOutputStream output = new FileOutputStream(temporary)) {
            output.write(value.getBytes(StandardCharsets.UTF_8));
            output.getFD().sync();
        }
        Files.move(temporary.toPath(), file.toPath(), StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING);
    }

    public Properties load() throws IOException {
        Properties state = new Properties();
        File file = new File(module, "effect.properties");
        if (file.isFile()) try (FileInputStream input = new FileInputStream(file)) { state.load(input); }
        if (!boot().equals(state.getProperty("boot"))) state.clear();
        return state;
    }

    public void save(Properties state) throws IOException {
        state.setProperty("boot", boot());
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        state.store(output, "AZJ2 runtime state; owned values only");
        write(new File(module, "effect.properties"), new String(output.toByteArray(), StandardCharsets.ISO_8859_1));
    }

    public void ready() throws IOException {
        write(new File(runtime, "ready"), "ready\n");
        log("PORT_READY");
    }

    public void fail(Exception error) {
        log("PORT_FAILURE " + error);
        stopping = true;
    }

    public void watch(Cleanup restore, Runnable tick) {
        cleanup = restore;
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try { clean(); } catch (Exception error) { log("PORT_RESTORE_PENDING " + error); }
        }, "port-shutdown"));
        Thread watcher = new Thread(() -> {
            try {
                long lastStamp = -1;
                long lastPulse = System.nanoTime();
                while (!stopping) {
                    File pulse = new File(runtime, "pulse");
                    long stamp = pulse.lastModified();
                    if (stamp != lastStamp) { lastStamp = stamp; lastPulse = System.nanoTime(); }
                    if (new File(module, "disable").exists() || new File(module, "remove").exists()
                            || new File(runtime, "stop").exists() || !pulse.isFile()
                            || System.nanoTime() - lastPulse > 10000000000L) break;
                    if (tick != null) tick.run();
                    Thread.sleep(250);
                }
                stopping = true;
                clean();
                log("PORT_STOPPED restoration confirmed");
                System.exit(0);
            } catch (Exception error) {
                log("PORT_RESTORE_PENDING " + error);
                System.exit(2);
            }
        }, "port-watchdog");
        watcher.setDaemon(true);
        watcher.start();
    }

    private synchronized void clean() throws Exception {
        stopping = true;
        if (cleaned.get()) return;
        cleanup.run();
        if (runtime.isDirectory()) write(new File(runtime, "restored"), "stock\n");
        cleaned.set(true);
    }

    /** Small command output only; readers with streaming output use their own process. */
    public static String command(String... args) throws Exception {
        Process process = new ProcessBuilder(args).redirectErrorStream(true).start();
        if (!process.waitFor(5, TimeUnit.SECONDS)) {
            process.destroyForcibly();
            throw new IOException("Command timed out: " + args[0]);
        }
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[1024];
        for (int size; (size = process.getInputStream().read(buffer)) != -1;) {
            output.write(buffer, 0, size);
            if (output.size() > 8192) throw new IOException("Command output exceeded limit");
        }
        String text = new String(output.toByteArray(), StandardCharsets.UTF_8).trim();
        if (process.exitValue() != 0) throw new IOException(args[0] + " failed: " + text);
        return text;
    }

    public static void log(String text) { System.out.println(text); }
}
