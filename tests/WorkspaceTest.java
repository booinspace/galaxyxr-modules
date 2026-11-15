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
        float[] capturedAnchor;
        public void check(){if(!live)throw new IllegalStateException("Host stopped");}
        public float[] anchor(){return anchor.clone();}
        public List<Workspace.Window> capture(float[] placement){capturedAnchor=placement.clone();return new ArrayList<>(current);}
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
    static float[] facing(float x,float y,float z,double yaw) {
        float c=(float)Math.cos(yaw),n=(float)Math.sin(yaw);
        float[] m=WorkspaceMath.identity();m[0]=2*c;m[2]=-2*n;m[5]=2;m[8]=2*n;m[10]=2*c;
        m[12]=x-2*n;m[13]=y;m[14]=z-2*c;return m;
    }
    static void followMotion() throws Exception {
        float[] start=facing(0,0,0,0),layout=WorkspaceMath.identity();layout[14]=-2;
        near(WorkspaceFollowMotion.head(start),WorkspaceMath.identity());
        WorkspaceFollowMotion motion=new WorkspaceFollowMotion(start,layout,0);
        for(int i=1;i<=30;i++)near(motion.update(facing(.04f,0,0,Math.toRadians(10)),i*33),layout);
        float[] target=facing(1,.7f,-.5f,Math.toRadians(45));
        for(int i=31;i<=150;i++)motion.update(target,i*33);
        float[] expected=WorkspaceMath.multiply(WorkspaceFollowMotion.head(target),layout),moved=motion.placement();
        for(int i=0;i<16;i++)check(Math.abs(expected[i]-moved[i])<.045,"Follow did not converge at "+i);
        float[] turn=facing(0,0,0,Math.toRadians(179));
        WorkspaceFollowMotion boundary=new WorkspaceFollowMotion(turn,layout,0);
        near(boundary.update(facing(0,0,0,Math.toRadians(-179)),33),layout);
        motion.rebase(target,moved,5000);near(motion.update(target,5033),moved);
        fails(()->motion.update(target,10));
        WorkspaceFollowMotion.WindowPose pose=new WorkspaceFollowMotion.WindowPose(layout,layout);
        float[] sent=pose.at(moved);pose.sent(sent,42,100);
        check(!pose.observe(layout,0,moved,110)&&pose.waiting(),"An old callback was mistaken for a user drag");
        check(!pose.observe(sent,42,moved,130)&&!pose.waiting(),"Own placement was mistaken for user input");
        float[] dragged=sent.clone();dragged[12]+=.3f;
        check(pose.observe(dragged,43,moved,140),"A native move did not pause following");near(pose.at(moved),dragged);
        float[] another=moved.clone();another[12]+=1;
        near(WorkspaceMath.relative(another,pose.at(another)),WorkspaceMath.relative(moved,dragged));
        WorkspaceFollowMotion.WindowPose stalled=new WorkspaceFollowMotion.WindowPose(layout,layout);
        stalled.sent(sent,42,0);fails(()->stalled.observe(layout,0,moved,501));
        float[] fine=layout.clone();fine[12]+=.0005f;
        check(WorkspaceFollowMotion.near(fine,layout)&&WorkspaceFollowMotion.placementChanged(fine,layout),"Slow follow motion was quantized to the larger input-recognition tolerance");
        WorkspaceFollowMotion wider=new WorkspaceFollowMotion(start,layout,0);
        for(int i=1;i<=30;i++)near(wider.update(facing(0,0,0,Math.toRadians(35)),i*11),layout);
        float[] first=wider.update(facing(0,0,0,Math.toRadians(90)),341);
        check(Math.abs(Math.atan2(first[8],first[10]))<Math.toRadians(.3),"Turning jumped instead of easing from rest");
        float previousYaw=(float)Math.atan2(first[8],first[10]);
        for(int i=1;i<=300;i++){
            float[] value=wider.update(facing(0,0,0,Math.toRadians(90)),341+i*11);
            float nextYaw=(float)Math.atan2(value[8],value[10]);
            check(Math.abs(nextYaw-previousYaw)<=Math.toRadians(60)*.011+.00001,"Turn rate cap was exceeded");previousYaw=nextYaw;
        }
        check(Math.abs(previousYaw-Math.PI/2)<Math.toRadians(1.1),"Smooth turning did not converge");
        WorkspaceFollowMotion pipelineMotion=new WorkspaceFollowMotion(start,layout,0);
        WorkspaceFollowMotion.WindowPose pipeline=new WorkspaceFollowMotion.WindowPose(layout,layout);
        List<float[]> queued=new ArrayList<>();
        for(int i=1;i<=8;i++){
            float[] frame=layout.clone();frame[12]=i*.02f;queued.add(frame);pipeline.sent(frame,100+i,i*10);
        }
        check(!pipeline.canSend(),"Unbounded placement pipeline");fails(()->pipeline.sent(layout,200,90));
        check(!pipeline.observe(queued.get(0),101,layout,100),"First late own reply was mistaken for a drag");
        check(pipeline.canSend()&&pipeline.waiting(),"Animation still waits for every reply");
        check(!pipeline.observe(queued.get(5),106,layout,110),"Coalesced acknowledgements were mistaken for a drag");
        check(!pipeline.observe(queued.get(1),102,layout,120),"An older queued callback was mistaken for a drag");
        float[] latestAnchor=layout.clone();latestAnchor[12]=2;
        near(WorkspaceMath.relative(latestAnchor,pipeline.at(latestAnchor)),WorkspaceMath.identity());
        float[] userMove=queued.get(5).clone();userMove[12]+=.3f;
        check(pipeline.observe(userMove,106,layout,130),"User move during the pipeline was lost");
        near(pipeline.at(layout),userMove);check(!pipeline.observe(userMove,106,layout,140),"A stationary held window repeatedly restarted the pause");
        check(!pipeline.observe(queued.get(7),108,layout,150),"A draining own reply overwrote user intent");near(pipeline.at(layout),userMove);
        WorkspaceFollowMotion.WindowPose sleeping=new WorkspaceFollowMotion.WindowPose(layout,layout);
        sleeping.sent(queued.get(0),501,0);sleeping.pause();
        check(!sleeping.waiting()&&!sleeping.observe(queued.get(0),501,layout,5000),"An idle tracking gap discarded the follow setting or looked like a drag");
        near(sleeping.at(layout),layout);
        pipelineMotion.pause(1000);near(pipelineMotion.update(start,1000),layout);
        float[] invalid=target.clone();invalid[0]=Float.NaN;fails(()->WorkspaceFollowMotion.head(invalid));
    }
    static float roll(float[] pose){return (float)Math.atan2(pose[1],pose[5]);}
    static float angularDistance(float a,float b){return (float)Math.abs(Math.atan2(Math.sin(a-b),Math.cos(a-b)));}
    static void headRollMotion() throws Exception {
        check(Math.abs(WorkspaceFollowMotion.gravityRoll(0,9.8f,0))<.001,"Upright gravity was not level");
        float right=WorkspaceFollowMotion.gravityRoll(-9.155f,2.901f,1.985f);
        check(right<-1.2f&&right>-1.3f,"Measured AZJ2 right tilt had the wrong sign");
        check(Math.abs(WorkspaceFollowMotion.gravityRoll(9.8f,0,0)-Math.PI/2)<.001,"Left side-lying roll was not 90 degrees");
        check(Math.abs(WorkspaceFollowMotion.gravityRoll(-9.8f,0,0)+Math.PI/2)<.001,"Right side-lying roll was not -90 degrees");
        check(Math.abs(WorkspaceFollowMotion.gravityRoll(0,7,7))<.001,"Head pitch became roll");
        check(Float.isNaN(WorkspaceFollowMotion.gravityRoll(0,0,9.8f)),"Vertical gaze produced an arbitrary roll");
        check(Float.isNaN(WorkspaceFollowMotion.gravityRoll(0,.5f,9.8f)),"Nearly vertical gaze did not hold the previous roll");
        check(Float.isNaN(WorkspaceFollowMotion.gravityRoll(Float.NaN,9.8f,0)),"NaN gravity was accepted");
        check(Float.isNaN(WorkspaceFollowMotion.gravityRoll(Float.POSITIVE_INFINITY,9.8f,0)),"Infinite gravity was accepted");
        check(Float.isNaN(WorkspaceFollowMotion.gravityRoll(0,0,0))&&Float.isNaN(WorkspaceFollowMotion.gravityRoll(0,20,0)),"Invalid gravity magnitude was accepted");
        float[] start=facing(0,0,0,0),layout=WorkspaceMath.identity();layout[14]=-2;
        WorkspaceFollowMotion motion=new WorkspaceFollowMotion(start,layout,0);
        for(int i=1;i<=30;i++)near(motion.update(start,(float)Math.toRadians(5),i*11),layout);
        float previous=0;
        for(int i=31;i<=400;i++){
            float[] value=motion.update(start,(float)-Math.PI/2,i*11);
            float next=roll(value);
            check(angularDistance(previous,next)<=Math.toRadians(90)*.011+.00001,"Roll exceeded its speed cap");
            if(i==31)check(Math.abs(next)<Math.toRadians(.3),"Roll jumped instead of easing from rest");
            previous=next;
        }
        check(angularDistance(previous,(float)-Math.PI/2)<Math.toRadians(.6),"Roll did not reach a side-lying pose");
        float[] tilted=motion.placement();
        float[] local=WorkspaceMath.identity();local[12]=.6f;local[13]=.4f;local[0]=.8f;local[2]=-.6f;local[8]=.6f;local[10]=.8f;
        float[] window=WorkspaceMath.restore(layout,local);
        WorkspaceFollowMotion.WindowPose pose=new WorkspaceFollowMotion.WindowPose(window,layout);
        float[] rotated=pose.at(tilted);
        check(Math.abs(rotated[12]-.4f)<.01&&Math.abs(rotated[13]+.6f)<.01,"Workspace windows did not roll together around the head");
        near(WorkspaceMath.relative(tilted,rotated),local);
        for(int i=401;i<=450;i++)near(motion.update(start,Float.NaN,i*11),tilted);
        near(motion.update(start,450*11),tilted);
        float[] copy=motion.placement();copy[0]=99;near(motion.placement(),tilted);
        WorkspaceFollowMotion resumed=new WorkspaceFollowMotion(start,tilted,0);
        for(int i=1;i<=100;i++)near(resumed.update(start,(float)-Math.PI/2,i*11),tilted);
        resumed.rebase(start,tilted,2000);near(resumed.update(start,(float)-Math.PI/2,2011),tilted);
        for(int i=451;i<=850;i++)motion.update(facing(1,0,0,0),Float.NaN,i*11);
        check(Math.abs(motion.placement()[12]-1)<.01,"Missing roll readings stopped positional following");
        check(angularDistance(roll(motion.placement()),roll(tilted))<.001,"Missing roll readings levelled the workspace");
        WorkspaceFollowMotion combined=new WorkspaceFollowMotion(start,layout,0);
        float[] target=facing(1,.7f,-.5f,Math.toRadians(60));
        for(int i=1;i<=600;i++)combined.update(target,(float)Math.PI/2,i*11);
        float[] expected=WorkspaceMath.identity();expected[0]=0;expected[1]=1;expected[4]=-1;expected[5]=0;
        expected=WorkspaceMath.multiply(WorkspaceMath.multiply(WorkspaceFollowMotion.head(target),expected),layout);
        for(int i=0;i<16;i++)check(Math.abs(combined.placement()[i]-expected[i])<.025,"Combined heading and roll changed layout geometry at "+i);
        float[] around=layout.clone();float c=(float)Math.cos(Math.toRadians(179)),s=(float)Math.sin(Math.toRadians(179));
        around[0]=c;around[1]=s;around[4]=-s;around[5]=c;
        WorkspaceFollowMotion wrap=new WorkspaceFollowMotion(start,around,0);
        near(wrap.update(start,(float)Math.toRadians(-179),11),around);
        previous=roll(around);
        for(int i=2;i<=400;i++){
            float next=roll(wrap.update(start,(float)Math.toRadians(-150),i*11));
            check(angularDistance(previous,next)<=Math.toRadians(90)*.011+.00001,"Roll took the long way around its wrap");previous=next;
        }
        check(angularDistance(previous,(float)Math.toRadians(-150))<Math.toRadians(.6),"Roll did not converge across 180 degrees");
    }
    public static void main(String[] ignored)throws Exception{
        followMotion();
        headRollMotion();
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
        check(!store.followEnabled(),"Follow me must default off");
        store.setFollowEnabled(true);check(new WorkspaceStore(root).followEnabled(),"Follow preference did not survive restart");
        check(Arrays.equals(valid,Files.readAllBytes(new File(root,"layouts.gxrw").toPath())),"Follow preference changed saved layouts");
        store.setFollowEnabled(false);check(!store.followEnabled(),"Follow preference did not turn off");
        Files.write(new File(root,"follow").toPath(),new byte[]{3});fails(store::followEnabled);
        Files.write(new File(root,"follow").toPath(),new byte[]{1,0});fails(store::followEnabled);
        Files.delete(new File(root,"follow").toPath());
        Files.createSymbolicLink(new File(root,"follow").toPath(),new File(root,"layouts.gxrw").toPath());
        fails(store::followEnabled);fails(()->store.setFollowEnabled(true));
        Files.delete(new File(root,"follow").toPath());
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
        float[] following=next.clone();engine.updatePlacementAnchor(following);following[12]=99;
        engine.autosave();near(host.capturedAnchor,next);
        float[] returned=engine.placementAnchor();returned[12]=99;near(engine.placementAnchor(),next);
        fails(()->engine.updatePlacementAnchor(singular));near(engine.placementAnchor(),next);
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
        System.out.println("PASS: view-relative transforms, plans, shared media, bounded storage, checksum, preflight, slow startup, no automatic rollback, cancellation, retry, journal, follow easing, wider turns, turn-rate cap, yaw wrap, gravity roll, side-lying layouts, roll easing/wrap/hold, rigid window geometry, bounded late/coalesced acknowledgements, drag preservation and moving-anchor persistence");
    }
}
