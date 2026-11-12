"""Exercise the real recorder with synthetic Android audio, then parse its WAV."""
import os
from pathlib import Path
import subprocess
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='gxr-mic-recording-') as temporary:
    root = Path(temporary)
    classes = root / 'classes'
    fixtures = {
        'android/os/Process.java': '''package android.os;
public class Process { public static int myUid() { return Integer.parseInt(System.getenv("MIC_TEST_UID")); } }''',
        'android/media/AudioFormat.java': '''package android.media;
public class AudioFormat { public static final int CHANNEL_IN_MONO=16, ENCODING_PCM_16BIT=2; }''',
        'android/media/MediaRecorder.java': '''package android.media;
public class MediaRecorder { public static class AudioSource { public static final int VOICE_PERFORMANCE=10; } }''',
        'android/media/AudioDeviceInfo.java': '''package android.media;
public class AudioDeviceInfo { public static final int TYPE_BUILTIN_MIC=15;
public int getType() { return "route".equals(System.getenv("MIC_TEST_FAIL"))?3:15; } }''',
        'android/media/MediaDataSource.java': '''package android.media;
public abstract class MediaDataSource {
public abstract int readAt(long position,byte[] buffer,int offset,int size) throws java.io.IOException;
public abstract long getSize() throws java.io.IOException;
public abstract void close() throws java.io.IOException;
}''',
        'android/media/MediaPlayer.java': '''package android.media;
public class MediaPlayer {
private int checks=0;
private MediaDataSource source;
public void setDataSource(MediaDataSource value) throws java.io.IOException {
 source=value;byte[] header=new byte[44];long size=value.getSize();
 if(value.readAt(0,header,0,44)!=44||header[0]!=82||header[8]!=87)throw new AssertionError("Invalid source header");
 if(value.readAt(size,header,0,2)!=-1||value.readAt(size-2,header,0,4)!=2||value.readAt(0,header,0,0)!=0)throw new AssertionError("Seek/EOF handling");
}
public void prepare() { if("play".equals(System.getenv("MIC_TEST_FAIL"))) throw new IllegalStateException("Decoder failure"); }
public void start() { new Thread(()->{try{Thread.sleep(60000);}catch(Exception ignored){}}).start(); }
public boolean isPlaying() { return "1".equals(System.getenv("MIC_TEST_LONG_PLAY"))||++checks<4; }
public void release() { try { if(source!=null)source.close();java.nio.file.Files.write(java.nio.file.Paths.get(System.getenv("MIC_TEST_TRACE")),new byte[]{2}); }catch(Exception e){throw new RuntimeException(e);} }
}''',
        'android/media/AudioRecord.java': '''package android.media;
public class AudioRecord {
public static final int STATE_INITIALIZED=1, RECORDSTATE_RECORDING=3, READ_NON_BLOCKING=1;
private int calls=0; private boolean recording=false;
public AudioRecord(int source,int rate,int channels,int encoding,int size) {
 if(source!=10||rate!=48000||channels!=16||encoding!=2||size<8192) throw new AssertionError("Wrong audio parameters");
}
public static int getMinBufferSize(int rate,int channels,int encoding) { return 8192; }
public int getState() { return 1; }
public void startRecording() { recording=true; }
public int getRecordingState() { return recording?3:1; }
public AudioDeviceInfo getRoutedDevice() {
 new Thread(()->{try{Thread.sleep(60000);}catch(Exception ignored){}}).start();
 return new AudioDeviceInfo();
}
public int read(byte[] data,int offset,int size,int mode) {
 if(!recording||mode!=READ_NON_BLOCKING) throw new AssertionError("Wrong recording state");
 if(++calls>65&&"read".equals(System.getenv("MIC_TEST_FAIL"))) return -3;
 for(int i=0;i<size;i++) data[offset+i]=(byte)(i%128);
 return size;
}
public void stop() { recording=false; }
public void release() {
 if(recording) throw new AssertionError("Microphone not stopped before release");
 try { java.nio.file.Files.write(java.nio.file.Paths.get(System.getenv("MIC_TEST_TRACE")),new byte[]{1}); }
 catch(Exception error) { throw new RuntimeException(error); }
}
}''',
    }
    sources = []
    for name, text in fixtures.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        sources.append(str(path))
    subprocess.run(['javac', '--release', '8', '-d', str(classes), *sources,
                    str(ROOT / 'modules/mic-gain-boost/src/com/gxr/mic/MicTest.java')], check=True)
    module = root / 'module'
    module.mkdir()
    trace = root / 'released'
    env = {**os.environ, 'MIC_TEST_UID': '0', 'MIC_TEST_TRACE': str(trace)}

    def run(command='capture', success=True, **extra):
        result = subprocess.run(['java', '-cp', str(classes), 'com.gxr.mic.MicTest', command, str(module)],
                                env={**env, **extra}, capture_output=True, text=True, timeout=15)
        assert (result.returncode == 0) == success, result.stderr

    run()
    clip = module / 'webroot/recordings/mic-test.wav'
    with wave.open(str(clip)) as recording:
        assert (recording.getnchannels(), recording.getsampwidth(), recording.getframerate(), recording.getnframes()) == (1, 2, 48000, 480000)
        assert recording.readframes(4) == bytes(range(8))
    assert trace.exists()
    original = clip.read_bytes()
    run('validate')
    run('play')
    assert trace.read_bytes() == bytes([2])
    (clip.parent / 'stop-playback').touch()
    run('play', MIC_TEST_LONG_PLAY='1')
    (clip.parent / 'stop-playback').unlink()
    run('play', success=False, MIC_TEST_FAIL='play')
    assert clip.read_bytes() == original
    clip.write_bytes(b'not a WAV')
    run('validate', success=False)
    clip.write_bytes(original)
    for failure in ('read', 'route'):
        trace.unlink()
        run(success=False, MIC_TEST_FAIL=failure)
        assert trace.exists(), 'Every opened microphone must be released'
        assert clip.read_bytes() == original, 'A failed attempt must preserve the previous clip'
        assert not clip.with_suffix('.wav.part').exists()
    run(success=False, MIC_TEST_UID='2000')
print('PASS: PCM/WAV capture, validation, native playback/stop, cleanup and explicit exit with live framework threads')
