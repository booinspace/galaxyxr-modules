import local.gxr.workspaces.*;
import java.io.File;
import java.nio.file.Files;
import java.util.*;

public final class WorkspaceTest {
    static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
    static Workspace.Window window(String pkg, int kind, float x) {
        float[] matrix = WorkspaceMath.identity(); matrix[12] = x;
        return new Workspace.Window(pkg + "/" + pkg + ".Main",kind,1200,800,false,matrix,new float[]{1,0,0,0},.25f);
    }
    static void near(float[] a, float[] b) {
        for (int i=0;i<16;i++) check(Math.abs(a[i]-b[i])<.001,"Matrix mismatch at " + i);
    }
    interface Failure { void run() throws Exception; }
    static void fails(Failure body) throws Exception {
        try {body.run();} catch(Exception expected){return;}
        throw new AssertionError("Invalid workspace accepted");
    }
    static final class Host implements WorkspaceEngine.Host {
        List<Workspace.Window> current = new ArrayList<>();
        List<String> events = new ArrayList<>();
        WorkspaceStore store;
        String failComponent="";
        float[] anchor=WorkspaceMath.identity();
        boolean live=true, failLaunchOnce, loseOnLaunch, failReady;
        long waitedMillis;
        public void check(){if(!live)throw new IllegalStateException("Host stopped");}
        public float[] anchor(){return anchor.clone();}
        public List<Workspace.Window> capture(float[] ignored){return new ArrayList<>(current);}
        public void preflight(Workspace.Window w){if(w.component.equals(failComponent))throw new IllegalArgumentException("App missing");}
        public void pause(Set<String> packages)throws Exception{
            WorkspaceTest.check(!store.read().pending.isEmpty(),"Changed audio before saving the switch journal");
            events.add("pause:"+new TreeSet<>(packages));
        }
        public void close(Workspace.Window w){events.add("close:"+w.packageName());current.removeIf(v->v.component.equals(w.component));}
        public void launch(Workspace.Window w){
            events.add("launch:"+w.packageName());
            if(loseOnLaunch){live=false;throw new IllegalStateException("Runtime lost");}
            current.add(w);
            if(failLaunchOnce){failLaunchOnce=false;throw new IllegalStateException("Launch accepted but still opening");}
        }
        public void foreground(Workspace.Window w){events.add("foreground:"+w.packageName());}
        public void awaitReady(Workspace.Window w)throws Exception{
            if(w.kind!=Workspace.Window.IMMERSIVE)return;
            WorkspaceWait.untilReady(()->waitedMillis>=65000?Boolean.TRUE:null,this::check,()->{
                WorkspaceTest.check(!store.read().pending.isEmpty(),"Marked the workspace complete while an app was opening");
                waitedMillis+=1000;
            });
            if(failReady)throw new InterruptedException("User stopped waiting");
        }
        public void restore(Workspace.Window w,float[] world){events.add("restore:"+w.packageName());}
        public void progress(String message){}
    }
    public static void main(String[] ignored)throws Exception{
        float[] previous=WorkspaceMath.identity();previous[12]=3;previous[14]=-2;
        float[] next=WorkspaceMath.identity();next[0]=0;next[2]=-1;next[8]=1;next[10]=0;next[12]=8;
        float[] world=WorkspaceMath.identity();world[12]=4;world[13]=1;world[14]=-4;
        float[] relative=WorkspaceMath.relative(previous,world);
        near(WorkspaceMath.restore(previous,relative),world);
        near(WorkspaceMath.relative(next,WorkspaceMath.restore(next,relative)),relative);
        near(WorkspaceMath.multiply(next,WorkspaceMath.inverse(next)),WorkspaceMath.identity());
        float[] invalid=world.clone();invalid[0]=Float.NaN;fails(()->WorkspaceMath.checked(invalid));
        float[] singular=world.clone();singular[0]=0;fails(()->WorkspaceMath.checked(singular));
        Workspace.Window old=window("app.old",0,1),shared=window("app.shared",0,2),pin=window("app.pin",1,0),vr=window("app.vr",2,0);
        WorkspacePlan plan=new WorkspacePlan(Arrays.asList(old,shared),Arrays.asList(shared,vr,pin));
        check(plan.keep.size()==1&&plan.close.equals(Collections.singletonList(old)),"Shared window was closed");
        check(plan.launch.equals(Arrays.asList(pin,vr)),"Immersive app must launch last");
        check(plan.pausePackages.equals(Collections.singleton("app.old")),"Paused unrelated or shared media");
        plan=new WorkspacePlan(Collections.singletonList(shared),Collections.singletonList(window("app.shared",1,0)));
        check(plan.close.size()==1&&plan.launch.size()==1&&plan.pausePackages.isEmpty(),"Overlay mode change must reopen but preserve shared media");
        plan=new WorkspacePlan(Collections.singletonList(window("app.vr",0,0)),Collections.singletonList(vr));
        check(plan.close.isEmpty()&&plan.launch.isEmpty()&&plan.keep.size()==1,"An immersive app's connection window was restarted");
        final int[] polls={0};
        fails(()->WorkspaceWait.untilReady(()->null,()->{if(++polls[0]>=4)throw new InterruptedException("Stopped");},()->{}));
        check(polls[0]==4,"Readiness ignored explicit cancellation/health loss");
        File root=Files.createTempDirectory("gxr-workspace-test-").toFile();
        WorkspaceStore store=new WorkspaceStore(root);
        WorkspaceStore.Index initial=store.read();
        check(initial.workspaces.size()==3&&initial.get(initial.active).name.equals("Desk"),"Default presets");
        Workspace desk=initial.get(initial.active).withWindows(Arrays.asList(old,shared));
        Workspace cinema=initial.workspaces.get(0).withWindows(Arrays.asList(shared,pin,vr));
        WorkspaceStore.Index ready=new WorkspaceStore.Index(initial.replace(desk).replace(cinema).workspaces,desk.id,"",true);
        store.save(ready);
        check(store.read().get(desk.id).windows.get(0).curvature==.25f,"Curvature round-trip");
        byte[] valid=Files.readAllBytes(new File(root,"layouts.gxrw").toPath());
        byte[] corrupt=valid.clone();corrupt[corrupt.length-1]^=1;
        Files.write(new File(root,"layouts.gxrw").toPath(),corrupt);fails(store::read);
        Files.write(new File(root,"layouts.gxrw").toPath(),valid);
        Host host=new Host();host.store=store;host.current.addAll(Arrays.asList(old,shared));
        WorkspaceEngine engine=new WorkspaceEngine(store,host);
        engine.acknowledge();engine.switchTo(cinema.id);
        check(store.read().active.equals(cinema.id)&&store.read().pending.isEmpty(),"Switch not committed");
        check(host.events.indexOf("launch:app.pin")<host.events.indexOf("launch:app.vr"),"VR launch order");
        check(host.waitedMillis>=65000,"A slow immersive startup was interrupted");
        check(!host.events.contains("close:app.shared"),"Shared app was restarted");
        engine.autosave();check(store.read().get(cinema.id).windows.size()==3,"Active workspace autosave");
        host.events.clear();host.failComponent=old.component;
        fails(()->engine.switchTo(desk.id));
        check(host.events.isEmpty()&&store.read().active.equals(cinema.id),"Preflight failure changed windows");
        store.save(ready);
        Host retry=new Host();retry.store=store;retry.current.addAll(Arrays.asList(old,shared));retry.failLaunchOnce=true;
        WorkspaceEngine failedLaunch=new WorkspaceEngine(store,retry);
        fails(()->failedLaunch.switchTo(cinema.id));
        check(store.read().pending.equals(cinema.id)&&!failedLaunch.bound(),"A partial switch was not retained");
        check(retry.current.stream().anyMatch(w->w.component.equals(pin.component)),"The opening app was closed automatically");
        check(!retry.events.contains("launch:app.old"),"Failed switch automatically reopened the previous workspace");
        retry.events.clear();failedLaunch.switchTo(cinema.id);
        check(store.read().pending.isEmpty()&&store.read().active.equals(cinema.id),"Manual retry did not finish opening the target");
        check(!retry.events.contains("close:app.pin")&&!retry.events.contains("launch:app.pin"),"Manual retry restarted an app that was already opening");
        store.save(ready);
        Host cancelled=new Host();cancelled.store=store;cancelled.current.addAll(Arrays.asList(old,shared));cancelled.failReady=true;
        WorkspaceEngine paused=new WorkspaceEngine(store,cancelled);fails(()->paused.switchTo(cinema.id));
        check(cancelled.current.size()==3&&store.read().pending.equals(cinema.id),"Stopping a readiness wait closed destination apps");
        check(!cancelled.events.contains("close:app.vr")&&!cancelled.events.contains("launch:app.old"),"Cancellation triggered rollback");
        store.save(ready);
        Host lost=new Host();lost.store=store;lost.current.addAll(Arrays.asList(old,shared));lost.loseOnLaunch=true;
        WorkspaceEngine interrupted=new WorkspaceEngine(store,lost);fails(()->interrupted.switchTo(cinema.id));
        check(store.read().pending.equals(cinema.id)&&!interrupted.bound(),"Runtime loss must retain the interrupted journal");
        check(store.read().get(desk.id).windows.size()==2,"Runtime loss overwrote the previous workspace");
        lost.live=true;lost.loseOnLaunch=false;
        WorkspaceEngine restarted=new WorkspaceEngine(store,lost);restarted.switchTo(desk.id);
        check(store.read().pending.isEmpty()&&lost.current.size()==2,"Previous workspace could not be recovered");
        Workspace sharedVrDesk=desk.withWindows(Arrays.asList(shared,vr));
        Workspace sharedVrCinema=cinema.withWindows(Arrays.asList(pin,vr));
        store.save(new WorkspaceStore.Index(ready.replace(sharedVrDesk).replace(sharedVrCinema).workspaces,desk.id,"",true));
        Host commonVr=new Host();commonVr.store=store;commonVr.current.addAll(sharedVrDesk.windows);
        new WorkspaceEngine(store,commonVr).switchTo(cinema.id);
        check(commonVr.events.contains("foreground:app.vr")&&!commonVr.events.contains("close:app.vr")&&!commonVr.events.contains("launch:app.vr"),"Shared immersive app was restarted");
        WorkspaceStore.Index unconfirmed=new WorkspaceStore.Index(ready.workspaces,desk.id,"",false);store.save(unconfirmed);
        Host unsafe=new Host();unsafe.store=store;
        WorkspaceEngine unacknowledged=new WorkspaceEngine(store,unsafe);fails(()->unacknowledged.switchTo(cinema.id));
        check(unsafe.events.isEmpty(),"Unconfirmed switch changed apps");
        fails(()->new Workspace(desk.id,"bad\nname",0,Collections.emptyList()));
        fails(()->new Workspace(desk.id,"Duplicate",0,Arrays.asList(old,old)));
        System.out.println("PASS: view-relative transforms, plans, shared media, bounded storage, checksum, preflight, slow startup, no automatic rollback, cancellation, retry and journal");
    }
}
