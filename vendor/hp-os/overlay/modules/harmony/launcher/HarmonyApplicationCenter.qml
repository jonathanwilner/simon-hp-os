import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import Quickshell
import Quickshell.Wayland
import qs
import qs.services
import qs.modules.common
import qs.modules.common.widgets
import qs.modules.harmony.design
import qs.modules.harmony.components

PanelWindow {
    id: root
    visible: GlobalStates.searchOpen && HarmonyStartState.applicationCenter
    screen: GlobalStates.focusedScreen ?? Quickshell.screens[0]
    anchors { top: true; left: true; right: true; bottom: true }
    // The PC Application Center leaves the live dock available below its sheet.
    margins.bottom: (Math.max(28, Math.min(64, Number(Config.options?.iris?.dock?.iconSize ?? 48))) + 32)
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "harmony-application-center"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    onVisibleChanged: {
        if (visible) Qt.callLater(() => {
            if (!root.visible) return
            openFolder = ""
            search.clear()
            grid.currentIndex = 0
            grid.positionViewAtBeginning()
            search.forceActiveFocus()
        })
        else {
            if (actions) actions.close()
            menuEntry = null
        }
    }
    property string query: ""
    property string openFolder: ""
    property var menuEntry: null
    readonly property var pins: Config.options?.dock?.pinnedApps ?? []
    readonly property string wallpaper: Wallpapers.currentMainWallpaperPath(WallpaperListener.getMonitorName(root.screen))
    function isChromeVariant(entry) {
        const id = String(entry?.id ?? "").replace(/\.desktop$/, "")
        const name = String(entry?.name ?? "")
        return /^Chrome on /i.test(name) || /chrome.*moonlight|moonlight.*chrome/i.test(id)
            || /^Chrome[A-Z]{2}(?:\s|$)/.test(name) || /^chrome[-_][a-z]{2}[-_]/i.test(id)
    }
    function isGooglebook(entry) {
        return /^hp-googlebook-/.test(String(entry?.id ?? ""))
    }
    readonly property var googlebookEntries: AppSearch.list.filter(entry => entry && isGooglebook(entry))
    readonly property var chromeEntries: AppSearch.list.filter(entry => entry && isChromeVariant(entry))
    readonly property var entries: {
        const terms = root.query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)
        const apps = root.openFolder === "Chrome" ? root.chromeEntries.slice()
            : root.openFolder === "Googlebook" ? root.googlebookEntries.slice()
            : AppSearch.list.filter(entry => entry && !isChromeVariant(entry) && !isGooglebook(entry))
        if (!root.openFolder && root.chromeEntries.length)
            apps.push({id: "harmony-chrome-folder", name: "Chrome", icon: "folder", isFolder: true})
        if (!root.openFolder && root.googlebookEntries.length)
            apps.push({id: "harmony-googlebook-folder", name: "Googlebook", icon: "folder", isFolder: true})
        if (terms.length) return apps.filter(entry => entry && terms.every(term =>
            (entry.name + " " + (entry.comment ?? "") + " " + entry.id).toLocaleLowerCase().includes(term)))
        return apps.sort((a, b) => String(a.name).localeCompare(String(b.name)))
    }
    function goBack() {
        if (openFolder) { openFolder = ""; search.clear(); grid.positionViewAtBeginning() }
        else GlobalStates.searchOpen = false
    }
    function pinned(entry) { return root.pins.some(id => String(id).toLowerCase() === String(entry.id).toLowerCase()) }
    function openEntry(entry, newWindow) {
        if (!entry) return
        if (entry.isFolder) { openFolder = entry.name; search.clear(); grid.currentIndex = 0; grid.positionViewAtBeginning(); return }
        const wanted = String(entry.id).replace(/\.desktop$/, "").toLowerCase()
        const existing = NiriService.windows.find(win => String(AppSearch.lookupDesktopEntry(win.app_id)?.id ?? win.app_id).replace(/\.desktop$/, "").toLowerCase() === wanted)
        if (existing && !newWindow) NiriService.focusWindow(existing.id)
        else if (!AppSearch.launchEntry(entry)) return
        GlobalStates.searchOpen = false
    }
    Image {
        asynchronous: true
        width: root.width
        // Continue the same crop through the dock rather than stretching the wallpaper.
        height: root.screen?.height ?? root.height
        source: root.wallpaper.length ? (root.wallpaper.startsWith("file:") ? root.wallpaper : "file://" + root.wallpaper) : ""
        fillMode: Image.PreserveAspectCrop
        sourceSize: Qt.size(root.width, root.screen?.height ?? root.height)
        visible: !HarmonyTokens.reducedTransparency
        layer.enabled: HarmonyTokens.quality !== "performance"
        layer.effect: MultiEffect { blurEnabled: true; blur: 1; blurMax: 64; autoPaddingEnabled: false }
    }
    Rectangle {
        anchors.fill: parent
        color: HarmonyTokens.reducedTransparency ? HarmonyTokens.surface
            : HarmonyTokens.dark ? "#60000000" : "#20000000"
    }
    MouseArea { anchors.fill: parent; onClicked: GlobalStates.searchOpen = false }
    TextField {
        id: search
        anchors.horizontalCenter: parent.horizontalCenter
        y: Math.max(32, (root.screen?.height ?? root.height) * 0.059)
        width: Math.min(460, root.width - 80)
        height: 48
        leftPadding: 40; rightPadding: 40
        placeholderText: HarmonyTokens.tr("Search", "搜索")
        horizontalAlignment: Text.AlignLeft
        font.family: HarmonyTokens.fontFamily; font.pixelSize: 18
        color: HarmonyTokens.reducedTransparency ? HarmonyTokens.text : "white"
        placeholderTextColor: HarmonyTokens.reducedTransparency ? HarmonyTokens.text : "#c0ffffff"
        background: Rectangle { color: "#30ffffff"; radius: height / 2 }
        MaterialSymbol {
            x: 14; anchors.verticalCenter: parent.verticalCenter
            text: "search"; iconSize: 20; color: search.color
        }
        Item {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            width: 40; height: 40; visible: search.text.length > 0
            MaterialSymbol { anchors.centerIn: parent; text: "cancel"; iconSize: 20; color: search.color }
            MouseArea { anchors.fill: parent; onClicked: { search.clear(); search.forceActiveFocus() } }
        }
        onTextChanged: { root.query = text; grid.currentIndex = 0; grid.positionViewAtBeginning() }
        Keys.onDownPressed: { grid.forceActiveFocus(); grid.currentIndex = 0 }
        Keys.onEscapePressed: root.goBack()
        onAccepted: root.openEntry(root.entries[0], false)
        Component.onCompleted: if (root.visible) forceActiveFocus()
    }
    Button {
        visible: root.openFolder.length > 0
        height: 30
        anchors.left: grid.left
        y: search.y + search.height + 8
        text: "‹ " + HarmonyTokens.tr("All apps", "所有应用") + "  /  " + root.openFolder
        onClicked: root.goBack()
    }
    GridView {
        id: grid
        readonly property int columns: Math.min(8, Math.max(3, Math.floor((root.width - 120) / 180)))
        width: Math.min(root.width - 80, columns * 205)
        anchors.horizontalCenter: parent.horizontalCenter
        y: search.y + search.height + Math.max(40, (root.screen?.height ?? root.height) * 0.054)
        height: parent.height - y - 24
        clip: true
        cellWidth: width / columns
        cellHeight: 179
        // Keep live DesktopEntry QObjects out of Qt's QVariant-list delegate model.
        // Qt 6.12 can dereference a stale metaobject when scrolling creates tiles.
        model: root.entries.length
        keyNavigationEnabled: true; currentIndex: 0
        Keys.onReturnPressed: root.openEntry(root.entries[currentIndex], false)
        Keys.onEnterPressed: root.openEntry(root.entries[currentIndex], false)
        Keys.onEscapePressed: root.goBack()
        Keys.onMenuPressed: { root.menuEntry = root.entries[currentIndex]; if (root.menuEntry && !root.menuEntry.isFolder) actions.popup() }
        delegate: Item {
            id: tile
            required property int index
            readonly property var entry: root.entries[index] ?? null
            width: grid.cellWidth; height: grid.cellHeight
            Rectangle {
                x: 6; y: 0; width: parent.width - 12; height: 156; radius: 24
                color: pointer.containsMouse || (grid.activeFocus && grid.currentIndex === tile.index) ? "#28ffffff" : "transparent"
                border.color: grid.activeFocus && grid.currentIndex === tile.index ? HarmonyTokens.focus : "transparent"
            }
            Image {
                id: appIcon
                asynchronous: true
                anchors.top: parent.top; anchors.topMargin: 18; anchors.horizontalCenter: parent.horizontalCenter
                width: 90; height: 90; sourceSize: Qt.size(180,180)
                source: AppSearch.resolveIcon(tile.entry?.icon ?? "", "application-x-executable"); fillMode: Image.PreserveAspectFit
            }
            MaterialSymbol {
                anchors.centerIn: appIcon
                visible: appIcon.status === Image.Error || appIcon.status === Image.Null
                text: "apps"; iconSize: 64
                color: HarmonyTokens.reducedTransparency ? HarmonyTokens.text : "white"
            }
            HarmonyText {
                anchors.top: parent.top; anchors.topMargin: 116
                anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 10
                height: 44; text: tile.entry?.name ?? ""; font.pixelSize: 18
                color: HarmonyTokens.reducedTransparency ? HarmonyTokens.text : "white"
                horizontalAlignment: Text.AlignHCenter; maximumLineCount: 2; elide: Text.ElideRight
            }
            MouseArea {
                id: pointer
                anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
                Accessible.role: Accessible.Button; Accessible.name: tile.entry?.name ?? ""
                onClicked: mouse => {
                    grid.currentIndex = tile.index
                    if (mouse.button === Qt.RightButton) { root.menuEntry = tile.entry; if (root.menuEntry && !root.menuEntry.isFolder) actions.popup() }
                    else root.openEntry(tile.entry, false)
                }
            }
        }
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        HarmonyText { anchors.centerIn: parent; visible: grid.count === 0; color: HarmonyTokens.reducedTransparency ? HarmonyTokens.text : "white"; text: HarmonyTokens.tr("No results", "无结果") }
    }
    Menu {
        id: actions
        MenuItem { text: HarmonyTokens.tr("Open", "打开"); onTriggered: root.openEntry(root.menuEntry, false) }
        MenuItem { text: HarmonyTokens.tr("New window", "新建窗口"); onTriggered: root.openEntry(root.menuEntry, true) }
        MenuItem { text: root.menuEntry && root.pinned(root.menuEntry) ? HarmonyTokens.tr("Unpin from dock", "从程序坞取消固定") : HarmonyTokens.tr("Pin to dock", "固定到程序坞"); onTriggered: { if (root.menuEntry) TaskbarApps.togglePin(root.menuEntry.id) } }
    }
}
