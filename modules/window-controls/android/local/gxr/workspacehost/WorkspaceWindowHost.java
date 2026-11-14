package local.gxr.workspacehost;

import android.content.Context;
import android.os.Handler;
import android.os.SystemClock;
import java.lang.reflect.Method;
import java.util.Map;
import java.util.HashMap;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import local.gxr.rotation.RotationController;

/** Narrow optional workspace bridge; Window Controls remains the sole owner of its window sessions. */
public final class WorkspaceWindowHost {
    public final Context context;
    public final Object repository;
    private final RotationController rotation;
    private volatile long heartbeat;
    private volatile boolean closed;
    private final Map<Integer,Float> curves = new ConcurrentHashMap<>();
    private final Map<Long,CompletableFuture<String>> pending = new ConcurrentHashMap<>();
    private final ConcurrentLinkedQueue<String> commands = new ConcurrentLinkedQueue<>();
    private final AtomicLong sequence = new AtomicLong();
    public WorkspaceWindowHost(Context context, Object repository, RotationController rotation) {
        this.context=context; this.repository=repository; this.rotation=rotation; pulse();
    }
    public void pulse(){heartbeat=SystemClock.uptimeMillis();}
    public boolean live(){return !closed&&SystemClock.uptimeMillis()-heartbeat<=5000;}
    public Handler owner(){return rotation.workspaceHandler();}
    public Object operations(){return rotation.workspaceOperations();}
    public boolean isHome(){return rotation.workspaceIsHome();}
    public Object desktopTask(int id)throws Exception{requireLive();return rotation.workspaceDesktopTask(id);}
    public void homeSpace()throws Exception{requireLive();rotation.workspaceHomeSpace();}
    public void preflightAppearance(float[] q,float curve){
        boolean rotated=Math.abs(q[0]-1)>.001||Math.abs(q[1])+Math.abs(q[2])+Math.abs(q[3])>.001;
        if(rotated&&!rotation.workspaceRotationEnabled())throw new IllegalStateException("Enable Rotation in Window Controls first");
        if(curve>0&&!local.gxr.rotation.WindowFeatures.curvature)throw new IllegalStateException("Enable Curvature in Window Controls first");
    }
    public void requireLive(){if(!live()||owner()==null)throw new IllegalStateException("Window Controls is not ready");}
    public float[] rotation(int task){return rotation.workspaceRotation(task);}
    public void setRotation(int task,float[] q)throws Exception{requireLive();
        if (!rotation.workspaceRotationEnabled() && Math.abs(q[0]-1)<.001 && Math.abs(q[1])+Math.abs(q[2])+Math.abs(q[3])<.001) return;
        rotation.restoreWorkspaceRotation(repository,task,q);}
    public float curvature(int task){Float value=curves.get(task);return value==null?0:value;}
    public void updateCurvatures(int[] ids,float[] values){
        if(ids.length!=values.length||ids.length>32)throw new IllegalArgumentException("Invalid curvature snapshot");
        Map<Integer,Float> next=new HashMap<>();
        for(int i=0;i<ids.length;i++)next.put(ids[i],values[i]);
        curves.keySet().retainAll(next.keySet());curves.putAll(next);
    }
    public void setCurvature(int task,float value)throws Exception{
        requireLive();
        if(!Float.isFinite(value)||value<0||value>1)throw new IllegalArgumentException("Invalid curvature");
        if(value==0&&curvature(task)==0)return;
        long id=sequence.incrementAndGet();
        CompletableFuture<String> reply=new CompletableFuture<>();pending.put(id,reply);
        commands.add(id+" "+task+" "+value);
        try{String error=reply.get(3,TimeUnit.SECONDS);if(!error.isEmpty())throw new IllegalStateException(error);}
        finally{pending.remove(id);}
    }
    public String poll(){String command=commands.poll();return command==null?"":command;}
    public void complete(long id,String error){CompletableFuture<String> future=pending.get(id);if(future!=null)future.complete(error);}
    public boolean requestLive(long id){return live()&&pending.containsKey(id);}
    public void configureWidth(Object session,int task)throws Exception{
        ClassLoader loader=session.getClass().getClassLoader();
        Class<?> width=loader.loadClass("local.gxr.curvature.CurvatureRange$WidthSource");
        Object source=java.lang.reflect.Proxy.newProxyInstance(loader,new Class<?>[]{width},(proxy,method,args)->{
            if(method.getName().equals("meters")){
                Object current=rotation.workspaceDesktopTask(task);
                if(current==null)throw new IllegalStateException("Workspace window closed");
                Object bounds=current.getClass().getMethod("getTaskBounds").invoke(current);
                int pixels=(Integer)bounds.getClass().getMethod("getRight").invoke(bounds)
                        -(Integer)bounds.getClass().getMethod("getLeft").invoke(bounds);
                if(pixels<=0)throw new IllegalStateException("Workspace window has no width");
                Class<?> metrics=context.getClassLoader().loadClass("com.android.systemui.xr.ui.DisplayMetrics");
                return metrics.getMethod("getPxToMeters",int.class).invoke(metrics.getField("INSTANCE").get(null),pixels);
            }
            if(method.getName().equals("hashCode"))return System.identityHashCode(proxy);
            if(method.getName().equals("equals"))return proxy==args[0];
            return "Workspace task width";
        });
        Method configure=session.getClass().getMethod("configureWidth",width);configure.invoke(session,source);
    }
    public void close(){closed=true;for(CompletableFuture<String> future:pending.values())future.complete("Workspace host stopped");pending.clear();commands.clear();}
}
