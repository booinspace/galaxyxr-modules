package com.gxr.mic;

import android.media.AudioDeviceInfo;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.media.MediaPlayer;
import android.media.MediaDataSource;
import android.os.Process;
import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.Arrays;

/** User-initiated, bounded PCM recording for the mic settings page. */
public final class MicTest {
    private static final int RATE = 48000;
    private static final int MAX_BYTES = RATE * 2 * 10;

    public static void main(String[] args) {
        int code = 0;
        try {
            if (Process.myUid() != 0 || args.length != 2) throw new IllegalArgumentException("Root, command and module directory required");
            File module = new File(args[1]).getCanonicalFile();
            if ("capture".equals(args[0])) record(module);
            else if ("validate".equals(args[0])) validate(new File(module, "webroot/recordings/mic-test.wav"));
            else if ("play".equals(args[0])) play(module);
            else throw new IllegalArgumentException("Unknown mic test command");
        } catch (Exception error) {
            error.printStackTrace(System.err);
            code = 1;
        }
        // Audio device queries leave framework threads alive after main returns.
        System.exit(code);
    }

    private static void record(File module) throws Exception {
        File directory = new File(module, "webroot/recordings");
        Files.createDirectories(directory.toPath());
        File partial = new File(directory, "mic-test.wav.part");
        File clip = new File(directory, "mic-test.wav");
        AudioRecord recorder = null;
        try {
            int minimum = AudioRecord.getMinBufferSize(RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
            if (minimum <= 0) throw new IOException("48 kHz microphone recording is unavailable");
            recorder = new AudioRecord(MediaRecorder.AudioSource.VOICE_PERFORMANCE, RATE,
                    AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, Math.max(minimum, 8192));
            if (recorder.getState() != AudioRecord.STATE_INITIALIZED) throw new IOException("Microphone could not be opened");
            recorder.startRecording();
            if (recorder.getRecordingState() != AudioRecord.RECORDSTATE_RECORDING) throw new IOException("Microphone did not start");
            // Let route selection and the gain helper settle before keeping samples.
            Thread.sleep(500);
            AudioDeviceInfo route = recorder.getRoutedDevice();
            if (route == null || route.getType() != AudioDeviceInfo.TYPE_BUILTIN_MIC) {
                throw new IOException("Use the built-in headset microphone for this test");
            }
            byte[] buffer = new byte[4096];
            for (int discard = 0; discard < 64; discard++) {
                int count = recorder.read(buffer, 0, buffer.length, AudioRecord.READ_NON_BLOCKING);
                if (count < 0) throw new IOException("Microphone read failed: " + count);
                if (count == 0) break;
            }
            int size = 0;
            long deadline = System.nanoTime() + 10000000000L;
            try (RandomAccessFile output = new RandomAccessFile(partial, "rw")) {
                output.setLength(0);
                output.write(new byte[44]);
                while (size < MAX_BYTES && System.nanoTime() < deadline) {
                    if (new File(module, "disable").exists() || new File(module, "remove").exists()) {
                        throw new IOException("Module disabled; recording stopped");
                    }
                    int count = recorder.read(buffer, 0, Math.min(buffer.length, MAX_BYTES - size), AudioRecord.READ_NON_BLOCKING);
                    if (count < 0) throw new IOException("Microphone read failed: " + count);
                    if (count == 0) { Thread.sleep(5); continue; }
                    output.write(buffer, 0, count);
                    size += count;
                }
                if (size < RATE * 2) throw new IOException("No usable microphone recording received");
                output.seek(0);
                output.write(header(size));
                output.getFD().sync();
            }
            recorder.stop();
            recorder.release();
            recorder = null;
            Files.move(partial.toPath(), clip.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } finally {
            if (recorder != null) {
                try { if (recorder.getRecordingState() == AudioRecord.RECORDSTATE_RECORDING) recorder.stop(); }
                finally { recorder.release(); }
            }
            Files.deleteIfExists(partial.toPath());
        }
    }

    private static void validate(File file) throws IOException {
        long size = file.length() - 44;
        if (size < RATE * 2 || size > MAX_BYTES || size % 2 != 0) throw new IOException("No valid microphone clip saved");
        byte[] actual = new byte[44];
        try (RandomAccessFile input = new RandomAccessFile(file, "r")) { input.readFully(actual); }
        if (!Arrays.equals(actual, header((int) size))) throw new IOException("Invalid microphone WAV header");
    }

    private static void play(File module) throws Exception {
        File clip = new File(module, "webroot/recordings/mic-test.wav");
        validate(clip);
        MediaPlayer player = new MediaPlayer();
        RandomAccessFile input = new RandomAccessFile(clip, "r");
        try {
            final long length = input.length();
            // This public reader avoids the context-dependent MediaProvider FD wrapper.
            player.setDataSource(new MediaDataSource() {
                @Override public synchronized int readAt(long position, byte[] buffer, int offset, int size) throws IOException {
                    if (position < 0) throw new IOException("Invalid audio offset");
                    if (size == 0) return 0;
                    if (position >= length) return -1;
                    input.seek(position);
                    return input.read(buffer, offset, Math.min(size, (int) (length - position)));
                }
                @Override public long getSize() { return length; }
                @Override public void close() throws IOException { input.close(); }
            });
            player.prepare();
            player.start();
            long deadline = System.nanoTime() + 12000000000L;
            while (player.isPlaying()) {
                if (new File(module, "webroot/recordings/stop-playback").exists()
                        || new File(module, "disable").exists() || new File(module, "remove").exists()) break;
                if (System.nanoTime() > deadline) throw new IOException("Playback timed out");
                Thread.sleep(25);
            }
        } finally {
            try { player.release(); } finally { input.close(); }
        }
    }

    private static byte[] header(int size) {
        ByteBuffer data = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN);
        data.putInt(0x46464952).putInt(36 + size).putInt(0x45564157);
        data.putInt(0x20746d66).putInt(16).putShort((short) 1).putShort((short) 1);
        data.putInt(RATE).putInt(RATE * 2).putShort((short) 2).putShort((short) 16);
        data.putInt(0x61746164).putInt(size);
        return data.array();
    }
}
