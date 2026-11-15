package local.gxr.workspaces;

import android.os.Handler;
import android.os.SystemClock;
import java.io.Closeable;
import java.io.IOException;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/** Samples an empty facing node and applies one rigid layout transform through stock placement. */
final class CpmFollow implements Closeable {
    private final CpmLayouts layouts;
    private final CpmFacing facing;
    private final WorkspaceFollowMotion motion;
    private final Map<Integer,WorkspaceFollowMotion.WindowPose> windows=new HashMap<>();
    private final Map<Integer,CpmLayouts.Reference> references=new HashMap<>();
    private float[] raw;
    private long holdUntil,statsAt,ticks,batches,blocked;
    private double slowest;
    private boolean closed,tracking=true;
    CpmFollow(CpmLayouts layouts,Handler owner,float[] placement)throws Exception{
        this.layouts=layouts;facing=new CpmFacing(layouts,owner);
        try{raw=facing.sample(2500);motion=new WorkspaceFollowMotion(raw,placement,SystemClock.uptimeMillis());}
        catch(Exception error){try{facing.close();}catch(Exception cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    void update(Set<Integer> ids)throws Exception{
        long began=System.nanoTime();
        try{updateWindows(ids);}finally{
            ticks++;slowest=Math.max(slowest,(System.nanoTime()-began)/1000000.0);
            long now=SystemClock.uptimeMillis();if(statsAt==0)statsAt=now;
            if(now-statsAt>=5000){
                android.util.Log.i("GxrWorkspaces","FOLLOW_TIMING tickHz="+(ticks*1000/(now-statsAt))+" batchHz="+(batches*1000/(now-statsAt))+" ackBlocked="+blocked+" maxTickMs="+Math.round(slowest));
                statsAt=now;ticks=0;batches=0;blocked=0;slowest=0;
            }
        }
    }
    private void updateWindows(Set<Integer> ids)throws Exception{
        if(closed)throw new IllegalStateException("Follow me stopped");
        if(ids.size()>Workspace.MAX_WINDOWS)throw new IllegalStateException("Follow me supports up to sixteen windows");
        long now=SystemClock.uptimeMillis();
        float[] latest=facing.poll(now);
        if(latest==null){
            motion.pause(now);
            if(tracking){tracking=false;for(WorkspaceFollowMotion.WindowPose pose:windows.values())pose.pause();android.util.Log.i("GxrWorkspaces","FOLLOW_WAITING_TRACKING");}
            return;
        }
        raw=latest;
        if(!tracking){tracking=true;android.util.Log.i("GxrWorkspaces","FOLLOW_TRACKING_RESUMED");}
        now=SystemClock.uptimeMillis();float[] anchor=motion.placement();
        windows.keySet().retainAll(ids);references.keySet().retainAll(ids);
        boolean full=false;
        Set<Integer> ready=new HashSet<>();
        Map<Integer,CpmLayouts.Reference> live=layouts.liveReferences(ids);
        for(Map.Entry<Integer,CpmLayouts.Reference> entry:live.entrySet()){
            int id=entry.getKey();CpmLayouts.Reference ref=entry.getValue();
            CpmLayouts.Snapshot sample=ref.latest;
            if(sample==null||!sample.attached)continue;
            if(references.get(id)!=ref){windows.put(id,new WorkspaceFollowMotion.WindowPose(sample.matrix,anchor));references.put(id,ref);}
            WorkspaceFollowMotion.WindowPose pose=windows.get(id);
            if(pose.observe(sample.matrix,sample.stamp,anchor,now))holdUntil=now+350;
            if(!pose.canSend())full=true;
            ready.add(id);
        }
        if(full){blocked++;return;}
        if(now<holdUntil){motion.rebase(raw,anchor,now);return;}
        float[] next=motion.update(raw,now);
        Map<Integer,float[]> moves=new HashMap<>();
        for(int id:ready){float[] world=windows.get(id).at(next);if(WorkspaceFollowMotion.placementChanged(world,references.get(id).matrix))moves.put(id,world);}
        if(!moves.isEmpty()){
            long stamp=System.nanoTime();Set<Integer> applied=layouts.placeMany(moves,stamp);batches++;
            for(int id:applied)windows.get(id).sent(moves.get(id),stamp,now);
        }
    }
    void settle()throws Exception{
        long until=SystemClock.uptimeMillis()+500;
        while(true){
            long now=SystemClock.uptimeMillis();boolean pending=false;
            for(Map.Entry<Integer,WorkspaceFollowMotion.WindowPose> item:windows.entrySet()){
                CpmLayouts.Reference ref=references.get(item.getKey());CpmLayouts.Snapshot sample=ref.latest;
                if(ref.disposed||sample==null||!sample.attached){item.getValue().pause();continue;}
                item.getValue().observe(sample.matrix,sample.stamp,motion.placement(),now);
                if(item.getValue().waiting())pending=true;
            }
            if(!pending)return;
            if(now>=until)throw new IllegalStateException("Window placement is still pending; layout was not saved");
            Thread.sleep(5);
        }
    }
    float[] savedWorld(int id,CpmLayouts.Reference ref,float[] actual,float[] anchor){
        WorkspaceFollowMotion.WindowPose pose=windows.get(id);
        if(pose==null||references.get(id)!=ref)return actual;
        CpmLayouts.Snapshot sample=ref.latest;long now=SystemClock.uptimeMillis();
        if(sample!=null&&sample.attached&&pose.observe(sample.matrix,sample.stamp,motion.placement(),now))holdUntil=now+350;
        return pose.at(anchor);
    }
    float[] placement(){return motion.placement();}
    @Override public void close()throws IOException{
        if(closed)return;facing.close();closed=true;windows.clear();references.clear();
        android.util.Log.i("GxrWorkspaces","FOLLOW_FROZEN");
    }
}
