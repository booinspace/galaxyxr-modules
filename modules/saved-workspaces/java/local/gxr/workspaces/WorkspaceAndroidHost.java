package local.gxr.workspaces;

import android.app.ActivityManager.RunningTaskInfo;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.graphics.Rect;
import android.media.AudioManager;
import android.media.AudioPlaybackConfiguration;
import android.media.session.MediaController;
import android.media.session.MediaSessionManager;
import android.os.Handler;
import android.os.SystemClock;
import android.util.Size;
import java.io.Closeable;
import java.io.File;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.function.BooleanSupplier;
import java.util.function.Consumer;

/** Native placement and owner-thread access; task launches/removals stay in the scoped root worker. */
final class WorkspaceAndroidHost implements WorkspaceEngine.Host, Closeable {
    private final Context context;
    private final Object bridge,repository;
    private final Handler owner;
    private final CpmLayouts layouts;
    private final WorkspaceIpc root;
    private final BooleanSupplier live;
    private final Consumer<String> status;
    private final Map<String,Workspace.Window> previous=new HashMap<>();
    private final Map<String,float[]> lastWorld=new HashMap<>();
    WorkspaceAndroidHost(Context context,Object bridge,File directory,String token,BooleanSupplier live,Consumer<String> status)throws Exception{
        this.context=context;this.bridge=bridge;this.live=live;this.status=status;
        repository=AndroidAccess.field(bridge,"repository");owner=(Handler)AndroidAccess.get(bridge,"owner");
        layouts=new CpmLayouts(context,bridge);root=new WorkspaceIpc(directory,token,live);
    }
    @Override public void check()throws Exception{
        if(!live.getAsBoolean())throw new IllegalStateException("Workspace service stopped; layouts were preserved");
        AndroidAccess.get(bridge,"requireLive");
    }
    @Override public float[] anchor()throws Exception{check();return layouts.facingAnchor();}
    private boolean pinned(RunningTaskInfo info)throws Exception{return AndroidAccess.mode(info)==4&&info.baseIntent!=null&&info.baseIntent.hasCategory("boo.puppy.gxr.PINNED_OVERLAY");}
    @Override public List<Workspace.Window> capture(float[] anchor)throws Exception{
        check();List<Workspace.Window> windows=new ArrayList<>();Set<Integer> ids=new HashSet<>();Map<String,Workspace.Window> next=new HashMap<>();
        for(RunningTaskInfo info:AndroidAccess.tasks()){
            if(!AndroidAccess.allowed(context,info))continue;
            Object desktop=AndroidAccess.on(owner,()->AndroidAccess.call(bridge,"desktopTask",new Class<?>[]{int.class},info.taskId));
            if(desktop==null)continue;
            boolean minimized=(Boolean)AndroidAccess.get(desktop,"getMinimized")||(Boolean)AndroidAccess.get(desktop,"getMinimizedRequested");
            int mode=AndroidAccess.mode(info);
            if(mode!=1&&!pinned(info)&&mode!=2&&mode!=3)continue;
            String pkg=info.baseActivity.getPackageName();
            Intent launcher=context.getPackageManager().getLaunchIntentForPackage(pkg);
            if(launcher==null||launcher.getComponent()==null)continue;
            String component=launcher.getComponent().flattenToString();
            Rect bounds=AndroidAccess.bounds(info);
            if(mode==2||mode==3){
                Workspace.Window item=new Workspace.Window(component,Workspace.Window.IMMERSIVE,Math.max(64,bounds.width()),Math.max(64,bounds.height()),false,WorkspaceMath.identity(),new float[]{1,0,0,0},0);
                if(next.put(component,item)!=null)throw new IllegalStateException("Close duplicate app windows before saving a workspace");
                windows.add(item);continue;
            }
            Object subspace=AndroidAccess.on(owner,()->AndroidAccess.call(repository,"getTaskSubspace",new Class<?>[]{int.class},info.taskId));
            if(subspace==null)continue;
            ids.add(info.taskId);
            float[] world;
            try{world=layouts.matrix(info.taskId);}catch(Exception unavailable){
                Workspace.Window cached=previous.get(component);
                if(cached!=null&&!AndroidAccess.visible(info)&&lastWorld.containsKey(component)){
                    Workspace.Window rebased=new Workspace.Window(cached.component,cached.kind,cached.width,cached.height,true,
                            WorkspaceMath.relative(anchor,lastWorld.get(component)),cached.rotation,cached.curvature);
                    if(next.put(component,rebased)!=null)throw new IllegalStateException("Close duplicate app windows before saving");windows.add(rebased);continue;
                }
                throw new IllegalStateException("Restore minimized windows once before saving their layout",unavailable);
            }
            lastWorld.put(component,world.clone());
            float[] rotation=(float[])AndroidAccess.on(owner,()->AndroidAccess.call(bridge,"rotation",new Class<?>[]{int.class},info.taskId));
            float curve=((Number)AndroidAccess.call(bridge,"curvature",new Class<?>[]{int.class},info.taskId)).floatValue();
            Workspace.Window item=new Workspace.Window(component,pinned(info)?Workspace.Window.PIN:Workspace.Window.HOME,
                    bounds.width(),bounds.height(),minimized,WorkspaceMath.relative(anchor,world),rotation,curve);
            if(next.put(component,item)!=null)throw new IllegalStateException("Close duplicate app windows before saving a workspace");
            windows.add(item);
        }
        if(windows.size()>Workspace.MAX_WINDOWS)throw new IllegalStateException("Close some windows before saving: maximum "+Workspace.MAX_WINDOWS);
        layouts.sweep(ids);previous.clear();previous.putAll(next);lastWorld.keySet().retainAll(next.keySet());return windows;
    }
    @Override public void preflight(Workspace.Window window)throws Exception{
        check();AndroidAccess.launch(context,window);
        AndroidAccess.call(bridge,"preflightAppearance",new Class<?>[]{float[].class,float.class},window.rotation,window.curvature);
        root.call(WorkspaceIpc.PREFLIGHT,window,0,"");
    }
    @Override public void pause(Set<String> packages)throws Exception{
        check();if(packages.isEmpty())return;
        Set<String> paused=new HashSet<>();
        MediaSessionManager sessions=(MediaSessionManager)context.getSystemService(Context.MEDIA_SESSION_SERVICE);
        if(sessions!=null)for(MediaController controller:sessions.getActiveSessions(null))if(packages.contains(controller.getPackageName())){
            controller.getTransportControls().pause();paused.add(controller.getPackageName());
        }
        AudioManager audio=(AudioManager)context.getSystemService(Context.AUDIO_SERVICE);
        for(AudioPlaybackConfiguration player:audio.getActivePlaybackConfigurations()){
            int usage=player.getAudioAttributes().getUsage();if(usage!=1&&usage!=14)continue;
            if(((Number)AndroidAccess.get(player,"getPlayerState")).intValue()!=2)continue;
            int uid=((Number)AndroidAccess.get(player,"getClientUid")).intValue();
            String[] names=context.getPackageManager().getPackagesForUid(uid);if(names==null)continue;
            boolean leaving=false;for(String name:names)if(packages.contains(name)&&!paused.contains(name))leaving=true;
            if(!leaving)continue;
            if(names.length!=1)throw new IllegalStateException("Pause shared-UID media manually before switching workspaces");
            Object proxy=AndroidAccess.get(player,"getPlayerProxy");if(proxy!=null)AndroidAccess.get(proxy,"pause");
        }
    }
    private RunningTaskInfo scan(Workspace.Window window,boolean allowLauncher)throws Exception{
        for(RunningTaskInfo info:AndroidAccess.tasks())if(info.baseActivity!=null&&info.baseActivity.getPackageName().equals(window.packageName())&&AndroidAccess.allowed(context,info)){
            int mode=AndroidAccess.mode(info);
            boolean matches=window.kind==Workspace.Window.PIN?pinned(info):window.kind==Workspace.Window.IMMERSIVE?
                    (mode==2||mode==3||(allowLauncher&&mode==1)):mode==1;
            if(matches)return info;
        }
        return null;
    }
    private RunningTaskInfo find(Workspace.Window window,boolean wait)throws Exception{
        check();
        if(!wait)return scan(window,false);
        return WorkspaceWait.untilReady(()->scan(window,true),this::check,()->Thread.sleep(100));
    }
    private void awaitPanel(int task)throws Exception{
        WorkspaceWait.untilReady(()->AndroidAccess.on(owner,()->{
            Object subspace=AndroidAccess.call(repository,"getTaskSubspace",new Class<?>[]{int.class},task);
            if(subspace==null)return null;
            boolean attached=Boolean.TRUE.equals(AndroidAccess.get(AndroidAccess.get(subspace,"isAttached"),"getValue"));
            boolean flat=Boolean.TRUE.equals(AndroidAccess.get(AndroidAccess.get(subspace,"is2DRenderingEnabled"),"getValue"));
            return attached&&flat?subspace:null;
        }),this::check,()->Thread.sleep(100));
    }
    @Override public void awaitReady(Workspace.Window window)throws Exception{
        RunningTaskInfo info=find(window,true);
        // An immersive app can legitimately start with its 2D connection/launcher window.
        if(window.kind==Workspace.Window.IMMERSIVE&&AndroidAccess.mode(info)==1)awaitPanel(info.taskId);
    }
    @Override public void close(Workspace.Window window)throws Exception{
        RunningTaskInfo info=find(window,false);if(info!=null)root.call(WorkspaceIpc.CLOSE,window,info.taskId,info.baseActivity.flattenToString());
    }
    @Override public void launch(Workspace.Window window)throws Exception{check();root.call(WorkspaceIpc.LAUNCH,window,0,"");}
    private void resize(RunningTaskInfo info,Workspace.Window window)throws Exception{
        Rect current=AndroidAccess.bounds(info);if(current.width()==window.width&&current.height()==window.height)return;
        CompletableFuture<Rect> ready=new CompletableFuture<>();
        AndroidAccess.on(owner,()->{
            check();Object operations=AndroidAccess.get(bridge,"operations");
            ClassLoader loader=operations.getClass().getClassLoader();Class<?> function=loader.loadClass("kotlin.jvm.functions.Function1");
            Object unit=loader.loadClass("kotlin.Unit").getField("INSTANCE").get(null);
            Object callback=Proxy.newProxyInstance(loader,new Class<?>[]{function},(proxy,method,args)->{
                if(method.getName().equals("invoke")){ready.complete(args[0]==null?null:new Rect((Rect)args[0]));return unit;}
                if(method.getName().equals("hashCode"))return System.identityHashCode(proxy);
                if(method.getName().equals("equals"))return proxy==args[0];return "Workspace resize completion";
            });
            AndroidAccess.call(operations,"resizeTask",new Class<?>[]{loader.loadClass("android.window.WindowContainerToken"),Size.class,function},
                    AndroidAccess.field(info,"token"),new Size(window.width,window.height),callback);
            return null;
        });
        Rect actual=ready.get(5,TimeUnit.SECONDS);if(actual==null||actual.isEmpty())throw new IllegalStateException("App could not restore its window size");
    }
    @Override public void restore(Workspace.Window window,float[] world)throws Exception{
        check();RunningTaskInfo info=find(window,true);
        AndroidAccess.on(owner,()->{check();AndroidAccess.call(AndroidAccess.get(bridge,"operations"),"restoreTask",
                new Class<?>[]{Class.forName("android.window.WindowContainerToken")},AndroidAccess.field(info,"token"));return null;});
        awaitPanel(info.taskId);
        resize(info,window);layouts.place(info.taskId,world);
        AndroidAccess.on(owner,()->{check();AndroidAccess.call(bridge,"setRotation",new Class<?>[]{int.class,float[].class},info.taskId,window.rotation);return null;});
        AndroidAccess.call(bridge,"setCurvature",new Class<?>[]{int.class,float.class},info.taskId,window.curvature);
        if(window.minimized)AndroidAccess.on(owner,()->{
            check();Object operations=AndroidAccess.get(bridge,"operations");Class<?> token=Class.forName("android.window.WindowContainerToken");
            Object tokens=java.lang.reflect.Array.newInstance(token,1);java.lang.reflect.Array.set(tokens,0,AndroidAccess.field(info,"token"));
            AndroidAccess.call(operations,"minimizeTasks",new Class<?>[]{tokens.getClass()},tokens);return null;
        });
    }
    @Override public void beginRestore()throws Exception{
        AndroidAccess.on(owner,()->{check();AndroidAccess.get(bridge,"homeSpace");return null;});
        WorkspaceWait.untilReady(()->Boolean.TRUE.equals(AndroidAccess.get(bridge,"isHome"))?Boolean.TRUE:null,
                this::check,()->Thread.sleep(50));
    }
    @Override public void foreground(Workspace.Window window)throws Exception{
        RunningTaskInfo info=find(window,true);
        AndroidAccess.on(owner,()->{
            check();AndroidAccess.call(AndroidAccess.get(bridge,"operations"),"restoreTask",
                    new Class<?>[]{Class.forName("android.window.WindowContainerToken")},AndroidAccess.field(info,"token"));return null;
        });
    }
    @Override public void progress(String value){status.accept(value);}
    @Override public void close()throws java.io.IOException{layouts.close();}
}
