pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.services
import qs.modules.common
import qs.modules.common.functions

Singleton {
    id: root
    property bool opened: false
    property var files: []
    property var apps: []
    property var pendingApps: []
    property string lastApp: ""
    signal accountDetailsRequested()
    function openAccountSettings() { accountSettingsProbe.running = true }
    Process {
        id: accountSettingsProbe
        command: ["sh", "-c", "hp-os-user-settings --available 2>/dev/null"]
        onExited: (exitCode, exitStatus) => {
            if (exitCode === 0) {
                ShellExec.execDetachedArgs(["hp-os-user-settings"])
                root.opened = false
            } else root.accountDetailsRequested()
        }
    }
    function showAll() { GlobalStates.searchOpen = true; opened = false }
    function lock() { Session.lock(); opened = false }
    function logOut() { Session.logout(); opened = false }
    function toggle() { opened = !opened }
    function refresh() { if (!listing.running) listing.running = true }
    function openApp(entry) {
        if (!entry) return
        const wanted = String(entry.id).replace(/\.desktop$/, "").toLowerCase()
        const existing = NiriService.windows.find(win => String(AppSearch.lookupDesktopEntry(win.app_id)?.id ?? win.app_id).replace(/\.desktop$/, "").toLowerCase() === wanted)
        if (existing) NiriService.focusWindow(existing.id)
        else if (!AppSearch.launchEntry(entry)) return
        opened = false
    }
    function openFile(url) { ShellExec.execDetachedArgs(["xdg-open", url]); opened = false }
    function observe() {
        const app = NiriService.activeWindow?.app_id
        const entry = app ? AppSearch.lookupDesktopEntry(app) : null
        if (!entry || entry.id === lastApp) return
        lastApp = entry.id
        pendingApps = [...pendingApps.filter(id => id !== entry.id), entry.id]
        drain()
    }
    function drain() {
        if (observer.running || pendingApps.length === 0) return
        observer.command = ["hp-os-recents", "observe-app", pendingApps[0]]
        pendingApps = pendingApps.slice(1)
        observer.running = true
    }
    onOpenedChanged: {
        if (opened) { GlobalStates.searchOpen = false; refresh() }
    }
    Connections {
        target: NiriService
        function onActiveWindowChanged() { root.observe() }
    }
    Connections {
        target: GlobalStates
        function onSearchOpenChanged() { if (GlobalStates.searchOpen) root.opened = false }
        function onScreenLockedChanged() { if (GlobalStates.screenLocked) root.opened = false }
    }
    Process {
        id: listing
        command: ["hp-os-recents", "list", "--limit", "32"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const result = JSON.parse(text)
                    root.files = (result.files ?? []).slice(0, 8)
                    root.apps = (result.apps ?? []).map(item => AppSearch.lookupDesktopEntry(item.id)).filter(Boolean).slice(0, 8)
                } catch (_) { root.files = []; root.apps = [] }
            }
        }
    }
    Process { id: observer; onExited: { if (root.opened) root.refresh(); root.drain() } }
}
