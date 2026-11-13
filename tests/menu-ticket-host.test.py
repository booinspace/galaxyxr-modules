"""Exercise the generated Java menu ticket's real queued-attachment lifecycle."""
import argparse
from pathlib import Path
import subprocess
import tempfile

SOURCES = {
    "android/view/View.java": """package android.view;
public final class View {
    public Object token = new Object(); public boolean reject; public Runnable queued;
    public Object getWindowToken() { return token; } public boolean isShown() { return token != null; }
    public boolean post(Runnable callback) { if (reject) return false; queued = callback; return true; }
    public void removeCallbacks(Runnable callback) { if (queued == callback) queued = null; }
    public void run() { Runnable next = queued; queued = null; if (next != null) next.run(); }
}
""",
    "local/gxr/curvature/CurvatureSession.java": """package local.gxr.curvature;
public final class CurvatureSession {
    public String status = "active"; public int getTaskId() { return 42; }
    public String getStatus() { return status; }
}
""",
    "local/gxr/curvature/MenuAttachment.java": """package local.gxr.curvature;
import android.view.View;
public final class MenuAttachment {
    public static final class Menu { public View root = new View(); public boolean fail; }
    public static int creates; private boolean closed;
    public static int getMenuTaskId(Object menu) { return 42; }
    public static View getMenuRoot(Object menu) { return ((Menu) menu).root; }
    public MenuAttachment(Object menu, CurvatureSession session) {
        creates++; if (((Menu) menu).fail) throw new IllegalStateException("fixture attachment failed");
    }
    public void close() { closed = true; } public boolean isClosed() { return closed; }
    public String getLayoutSummary() { return "attached"; } public String getLastError() { return null; }
}
""",
    "local/gxr/curvature/MenuTicketTest.java": """package local.gxr.curvature;
public final class MenuTicketTest {
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    public static void main(String[] args) throws Exception {
        MenuAttachment.Menu menu = new MenuAttachment.Menu();
        MenuAttachmentTicket ticket = new MenuAttachmentTicket(menu, new CurvatureSession());
        menu.root.token = null; menu.root.run();
        check(ticket.isClosed() && !ticket.isAttached() && ticket.getLastError() == null && MenuAttachment.creates == 0);
        ticket.close();
        menu = new MenuAttachment.Menu();
        ticket = new MenuAttachmentTicket(menu, new CurvatureSession()); ticket.close(); menu.root.run();
        check(ticket.isClosed() && MenuAttachment.creates == 0);
        menu = new MenuAttachment.Menu(); CurvatureSession session = new CurvatureSession();
        ticket = new MenuAttachmentTicket(menu, session); session.status = "restored"; menu.root.run();
        check(ticket.isClosed() && ticket.getLastError() == null && MenuAttachment.creates == 0);
        ticket.close();
        menu = new MenuAttachment.Menu(); ticket = new MenuAttachmentTicket(menu, new CurvatureSession()); menu.root.run();
        check(ticket.isAttached() && !ticket.isClosed() && ticket.getLastError() == null && MenuAttachment.creates == 1);
        ticket.close(); check(ticket.isClosed());
        menu = new MenuAttachment.Menu(); menu.fail = true;
        ticket = new MenuAttachmentTicket(menu, new CurvatureSession()); menu.root.run();
        check(ticket.getLastError().contains("fixture attachment failed")); ticket.close();
        menu = new MenuAttachment.Menu(); menu.root.reject = true;
        try (MenuAttachmentTicket rejected = new MenuAttachmentTicket(menu, new CurvatureSession())) {
            throw new AssertionError("Rejected post accepted: " + rejected.isAttached());
        }
        catch (IllegalStateException expected) { check(expected.getMessage().contains("Could not post")); }
        System.out.println("PASS: closed-menu cancellation, stale session, queued close and real attachment errors");
    }
}
""",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticket", type=Path)
    parser.add_argument("--java", required=True, type=Path)
    parser.add_argument("--ecj", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gxr-menu-ticket-") as directory:
        work = Path(directory)
        sources = []
        for name, source in SOURCES.items():
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)
            sources.append(str(path))
        sources.append(str(args.ticket))
        output = work / "classes"
        subprocess.run([str(args.java), "-jar", str(args.ecj), "-source", "1.8", "-target", "1.8", "-proc:none",
                        "-failOnWarning", "-d", str(output), *sources], check=True)
        subprocess.run([str(args.java), "-cp", str(output), "local.gxr.curvature.MenuTicketTest"], check=True)


if __name__ == "__main__":
    main()
