package local.gxr.workspaces;

import android.app.ActivityManager.RunningTaskInfo;
import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.os.Looper;
import android.os.SystemClock;
import android.system.Os;
import android.system.OsConstants;
import android.util.Base64;
import com.gxr.port.PortRuntime;
import java.io.File;
import java.io.FileDescriptor;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/** Root only transports the module helper and performs bounded, validated task operations. */
public final class WorkspaceRoot {
    private static final File CONTROL=new File("/dev/gxr-window-curvature/control");
    private static final File WINDOWS=new File("/data/adb/modules/gxr_window_curvature");
    private final PortRuntime runtime;
    private final Context context;
    private final String token=UUID.randomUUID().toString().replace("-","");
    private final List<File> directories=new ArrayList<>();
    private final int systemUid;
    private volatile String target="";
    private String lastRequest="", lastStatus="";
    private long lastPing;
    private long lastError;
    private WorkspaceRoot(PortRuntime runtime)throws Exception{
        this.runtime=runtime;
        Object thread=Class.forName("android.app.ActivityThread").getMethod("systemMain").invoke(null);
        context=(Context)AndroidAccess.get(thread,"getSystemContext");
        ApplicationInfo app=context.getPackageManager().getApplicationInfo("com.android.systemui",0);
        systemUid=app.uid;
        for(String root:new String[]{app.dataDir,app.deviceProtectedDataDir})if(root!=null){
            File directory=new File(new File(root,"files"),"booinspace-workspaces");
            if(!directories.contains(directory))directories.add(directory);
        }
    }
    private static void frame(String line)throws Exception{
        byte[] bytes=(line+"\n").getBytes(StandardCharsets.US_ASCII);
        if(bytes.length>3500)throw new IllegalArgumentException("Workspace frame too large");
        FileDescriptor fd=Os.open(CONTROL.getPath(),OsConstants.O_WRONLY|OsConstants.O_NONBLOCK,0);
        try{
            long until=SystemClock.uptimeMillis()+1500;
            while(true){
                try{if(Os.write(fd,bytes,0,bytes.length)!=bytes.length)throw new java.io.IOException("Partial workspace frame");return;}
                catch(android.system.ErrnoException error){if(error.errno!=OsConstants.EAGAIN||SystemClock.uptimeMillis()>=until)throw error;Thread.sleep(20);}
            }
        }finally{Os.close(fd);}
    }
    private boolean hostReady()throws Exception{
        if(new File(WINDOWS,"disable").exists()||new File(WINDOWS,"remove").exists()||!CONTROL.exists())return false;
        String properties=new String(WorkspaceFiles.read(new File(WINDOWS,"module.prop"),8192),StandardCharsets.UTF_8);
        int code=0;
        for(String line:properties.split("\n"))if(line.startsWith("versionCode="))code=Integer.parseInt(line.substring(12).trim());
        if(code<171)return false;
        File status=new File("/dev/gxr-window-curvature/status");
        return status.isFile()&&new String(WorkspaceFiles.read(status,4096),StandardCharsets.UTF_8).startsWith("RUNNING");
    }
    private void connect()throws Exception{
        String next=new String(WorkspaceFiles.read(new File("/dev/gxr-window-curvature/target"),512),StandardCharsets.US_ASCII).trim();
        if(!next.matches("[0-9a-f-]{36}:[1-9][0-9]*:[1-9][0-9]*"))throw new IllegalStateException("Invalid window host identity");
        if(next.equals(target))return;
        byte[] dex=WorkspaceFiles.read(new File(runtime.module,"bin/helper.dex"),512*1024);
        StringBuilder sha=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(dex))sha.append(String.format("%02x",b&255));
        String payload=Base64.encodeToString(dex,Base64.NO_WRAP);
        frame("ws-begin "+token+" "+sha+" "+dex.length);
        for(int i=0;i<payload.length();i+=2800)frame("ws-part "+token+" "+payload.substring(i,Math.min(i+2800,payload.length())));
        frame("ws-end "+token);
        target=next;
        PortRuntime.log("WORKSPACES_HELPER_SENT - waiting for native Recents UI");
    }
    private void requireHost()throws Exception{
        if(runtime.stopping||new File(runtime.module,"disable").exists()||new File(runtime.module,"remove").exists()||target.isEmpty()||!hostReady())throw new IllegalStateException("Workspace host stopped");
        String actual=new String(WorkspaceFiles.read(new File("/dev/gxr-window-curvature/target"),512),StandardCharsets.US_ASCII).trim();
        if(!target.equals(actual))throw new IllegalStateException("SystemUI changed during the workspace switch");
        String[] identity=actual.split(":");
        String stat=new String(WorkspaceFiles.read(new File("/proc/"+identity[1]+"/stat"),8192),StandardCharsets.US_ASCII);
        String[] fields=stat.substring(stat.lastIndexOf(')')+1).trim().split("\\s+");
        if(!identity[0].equals(PortRuntime.boot())||fields.length<20||!identity[2].equals(fields[19]))throw new IllegalStateException("Previous SystemUI process ended");
    }
    private int operation(WorkspaceIpc.Request request)throws Exception{
        requireHost();
        request.fresh();
        Workspace.Window window=new Workspace.Window(request.component,request.kind,1200,800,false,WorkspaceMath.identity(),new float[]{1,0,0,0},0);
        AndroidAccess.launch(context,window);
        if(request.action==WorkspaceIpc.PREFLIGHT)return 0;
        requireHost();
        if(request.action==WorkspaceIpc.CLOSE){
            for(RunningTaskInfo info:AndroidAccess.tasks())if(info.taskId==request.task){
                int mode=AndroidAccess.mode(info);
                if(!AndroidAccess.allowed(context,info)||!info.baseActivity.flattenToString().equals(request.expectedBase)
                        ||!info.baseActivity.getPackageName().equals(window.packageName())||mode<1||mode>4
                        ||(mode==4&&(info.baseIntent==null||!info.baseIntent.hasCategory("boo.puppy.gxr.PINNED_OVERLAY")))){
                    throw new IllegalStateException("Window changed before closing; saved layout was preserved");
                }
                request.fresh();
                requireHost();
                Object service=AndroidAccess.staticCall("android.app.ActivityTaskManager","getService",new Class<?>[0]);
                if(!Boolean.TRUE.equals(AndroidAccess.invoke(Class.forName("android.app.IActivityTaskManager").getMethod("removeTask",int.class),service,info.taskId)))throw new IllegalStateException("Could not close app window");
                return info.taskId;
            }
            return 0;
        }
        requireHost();
        if(window.kind==Workspace.Window.PIN)command("/system/bin/sh",new File(WINDOWS,"pins.sh").getPath(),"pin",window.packageName());
        else command("/system/bin/am","start","--user","0","-a","android.intent.action.MAIN","-c","android.intent.category.LAUNCHER","-n",window.component);
        // The command acknowledges the launch. The native worker waits for the actual window separately.
        return 0;
    }
    private void requests()throws Exception{
        for(File directory:directories){
            File file=new File(directory,"request.bin");
            if(!file.isFile())continue;
            if(Files.isSymbolicLink(directory.toPath())||Os.stat(directory.getPath()).st_uid!=systemUid||Os.stat(file.getPath()).st_uid!=systemUid)throw new SecurityException("Workspace request owner changed");
            WorkspaceIpc.Request request=WorkspaceIpc.read(file);
            if(!request.token.equals(token)||request.id.equals(lastRequest))continue;
            lastRequest=request.id;
            try{int task=operation(request);WorkspaceIpc.reply(new File(runtime.runtime,"replies"),request,true,task,"",systemUid);}
            catch(Exception error){WorkspaceIpc.reply(new File(runtime.runtime,"replies"),request,false,0,error.getMessage()==null?error.toString():error.getMessage(),systemUid);}
        }
    }
    private void tick()throws Exception{
        if(!hostReady()){target="";return;}
        connect();
        requests();
        for(File directory:directories){
            File status=new File(directory,"frontend.txt");
            if(!status.isFile()||Os.stat(status.getPath()).st_uid!=systemUid)continue;
            String value=new String(WorkspaceFiles.read(status,8192),StandardCharsets.UTF_8);
            if(value.startsWith(token+"\n")&&!value.equals(lastStatus)){
                PortRuntime.write(new File(runtime.module,"frontend.status"),value.substring(33)+"\n");lastStatus=value;
            }
        }
    }
    private void stop()throws Exception{
        if(!target.isEmpty()&&CONTROL.exists())try{frame("ws-off "+token);Thread.sleep(6000);}catch(Exception error){PortRuntime.log("WORKSPACES_STOP - native heartbeat cleanup will finish: "+error);}
    }
    private static void command(String...args)throws Exception{
        java.lang.Process process=new ProcessBuilder(args).redirectErrorStream(true).start();
        Thread drain=new Thread(()->{try(java.io.InputStream in=process.getInputStream()){byte[] b=new byte[1024];while(in.read(b)!=-1){/* Drain without storing app launch output. */}}catch(Exception ignored){}});
        drain.setDaemon(true);drain.start();
        try{
            process.getOutputStream().close();
            if(!process.waitFor(12,TimeUnit.SECONDS))throw new IllegalStateException("App launch timed out");
            drain.join(500);
            if(process.exitValue()!=0)throw new IllegalStateException("Could not launch app");
        }finally{process.destroyForcibly();}
    }
    @SuppressWarnings("deprecation")
    public static void main(String[] args){
        try{
            if(android.os.Process.myUid()!=0)throw new SecurityException("Root required");
            if(args.length!=2)throw new IllegalArgumentException("Expected daemon or restore and module directory");
            Looper.prepareMainLooper();
            PortRuntime runtime=new PortRuntime(args[1]);
            WorkspaceRoot root=new WorkspaceRoot(runtime);
            if(args[0].equals("restore")){if(CONTROL.exists())try{frame("ws-stop");Thread.sleep(6000);}catch(Exception ignored){}System.exit(0);return;}
            if(!args[0].equals("daemon"))throw new IllegalArgumentException("Unknown workspace command");
            PortRuntime.write(new File(runtime.module,"frontend.status"),"Waiting for Window Controls 0.1.70+\n");
            File replies=new File(runtime.runtime,"replies");
            if(!replies.mkdir())throw new IllegalStateException("Cannot create root-owned response directory");
            Os.chown(replies.getPath(),0,root.systemUid);Os.chmod(replies.getPath(),0710);
            File privateFiles=null;
            for(File candidate:root.directories)if(candidate.getParentFile().isDirectory()){privateFiles=candidate.getParentFile();break;}
            if(privateFiles==null)throw new IllegalStateException("SystemUI private files are not available");
            // Unix group permissions alone do not grant access to a default /dev SELinux label.
            WorkspaceFiles.inheritContext(replies,privateFiles);
            Os.chmod(runtime.runtime.getPath(),0711);
            runtime.watch(root::stop,()->{
                if(!root.target.isEmpty()&&SystemClock.uptimeMillis()-root.lastPing>=750){
                    try{frame("ws-ping "+root.token);root.lastPing=SystemClock.uptimeMillis();}
                    catch(Exception error){root.target="";PortRuntime.log("WORKSPACES_HEARTBEAT_ERROR "+error);}
                }
            });
            PortRuntime.write(new File(runtime.runtime,"ready"),"workspace bridge waiting for Window Controls 0.1.70+\n");
            PortRuntime.log("WORKSPACES_ROOT_READY - saved layouts and previews stay private on the headset");
            while(!runtime.stopping){try{root.tick();}catch(Exception error){if(SystemClock.uptimeMillis()-root.lastError>5000){PortRuntime.log("WORKSPACES_ROOT_ERROR "+error);root.lastError=SystemClock.uptimeMillis();}root.target="";}Thread.sleep(250);}
        }catch(Throwable error){error.printStackTrace(System.out);System.exit(1);}
    }
}
