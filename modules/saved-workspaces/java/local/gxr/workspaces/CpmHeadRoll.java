package local.gxr.workspaces;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.Handler;
import android.os.SystemClock;
import java.io.Closeable;

/** Owns a gravity listener for head roll while Follow me is active. */
final class CpmHeadRoll implements Closeable {
    private static final class Sample {
        final float angle;final long time;
        Sample(float angle,long time){this.angle=angle;this.time=time;}
    }
    private final SensorManager manager;
    private volatile Sample sample;
    private volatile boolean closed;
    private boolean registered;
    private final SensorEventListener listener=new SensorEventListener(){
        @Override public void onSensorChanged(SensorEvent event){
            if(closed||event.values.length<3)return;
            float angle=WorkspaceFollowMotion.gravityRoll(event.values[0],event.values[1],event.values[2]);
            sample=new Sample(angle,event.timestamp);
        }
        @Override public void onAccuracyChanged(Sensor ignored,int accuracy){}
    };
    CpmHeadRoll(Context context,Handler owner){
        manager=(SensorManager)context.getSystemService(Context.SENSOR_SERVICE);
        Sensor gravity=manager==null?null:manager.getDefaultSensor(Sensor.TYPE_GRAVITY);
        if(gravity==null)throw new IllegalStateException("Head-roll gravity sensor is unavailable");
        registered=manager.registerListener(listener,gravity,SensorManager.SENSOR_DELAY_GAME,owner);
        if(!registered)throw new IllegalStateException("Could not start head-roll tracking");
    }
    float value(){
        Sample value=sample;if(closed||value==null)return Float.NaN;
        long age=SystemClock.elapsedRealtimeNanos()-value.time;
        return age>=0&&age<=250000000L?value.angle:Float.NaN;
    }
    @Override public void close(){
        closed=true;
        if(registered){manager.unregisterListener(listener);registered=false;}
        sample=null;
    }
}
