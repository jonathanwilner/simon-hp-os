import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.services
import qs.modules.common
import qs.modules.hpos.design
import qs.modules.hpos.settings
import qs.modules.hpos.launcher

Item {
    id: root
    property bool preferencesOpen: false
    property bool galleryOpen: false
    // Reuse the application grid after its first open; hidden windows do not
    // hold a layer surface or keyboard focus. No polling is needed.
    property bool applicationCenterLoaded: false
    Connections {
        target: GlobalStates
        function onSearchOpenChanged() {
            if (GlobalStates.searchOpen) root.applicationCenterLoaded = true
        }
    }
    Process { id: touchCommand }
    function validatePreferences() {
        const p = Config.options.hpos
        if (p.schemaVersion < 1) Config.setNestedValue("hpos.schemaVersion", 1)
        // Future versions are left untouched so a downgrade does not destroy preferences.
        if (p.schemaVersion > 1) return
        for (const item of [ ["appearance", ["auto", "light", "dark"], "auto"],
                ["quality", ["full", "balanced", "performance"], "balanced"],
                ["locale", ["auto", "en_US", "zh_CN"], "auto"] ]) {
            if (!item[1].includes(p[item[0]])) Config.setNestedValue("hpos." + item[0], item[2])
        }
        if (!Number.isFinite(p.materialIntensity) || p.materialIntensity < 0.5 || p.materialIntensity > 1.5)
            Config.setNestedValue("hpos.materialIntensity", 1.0)
    }
    LazyLoader {
        active: (root.applicationCenterLoaded || GlobalStates.searchOpen) && Config.options.hpos.applicationCenter
        component: HposApplicationCenter {}
    }
    LazyLoader {
        active: true // Keep native layer surfaces alive across Start toggles.
        component: HposStartMenu { onSettingsRequested: root.preferencesOpen = true }
    }
    Component.onCompleted: { validatePreferences(); HposStartState.observe() }
    IpcHandler {
        target: "hpos"
        function applications(): void { HposStartState.showAll() }
        function search(): void { HposStartState.toggleSearch() }
        function start(): void { HposStartState.toggle() }
        function settings(): void { root.preferencesOpen = true }
        function gallery(): void { root.galleryOpen = true }
        function close(): void { HposStartState.opened = false; root.galleryOpen = false; root.preferencesOpen = false }
        function keyboard(): void { touchCommand.command = ["touch-support", "toggle"]; touchCommand.running = true }
        function touchSettings(): void { touchCommand.command = ["touch-support", "settings"]; touchCommand.running = true }
        function controlCenter(): void { GlobalStates.controlPanelOpen = !GlobalStates.controlPanelOpen }
        function printing(): void { GlobalStates.irisControlPickerRequest = "printing"; GlobalStates.controlPanelOpen = true }
        function sharing(): void { GlobalStates.irisControlPickerRequest = "omdrop"; GlobalStates.controlPanelOpen = true }
        function notifications(): void { GlobalStates.toggleSidebarRight("") }
        function set(key: string, value: string): bool {
            let parsed = value
            try { parsed = JSON.parse(value) } catch (_) {}
            return HposTokens.setPreference(key, parsed)
        }
        function status(): string {
            return JSON.stringify({searchOpen: GlobalStates.searchOpen && !HposStartState.applicationCenter, applicationCenterOpen: GlobalStates.searchOpen && HposStartState.applicationCenter, startOpen: HposStartState.opened, recentFiles: HposStartState.files.length, recentApps: HposStartState.apps.length, family: Config.options.panelFamily, font: HposTokens.fontFamily,
                genuineFont: HposTokens.genuineFontAvailable, dark: HposTokens.dark,
                quality: HposTokens.quality, locale: HposTokens.preferences.locale, notificationCount: Notifications.list.length,
                audioReady: Audio.ready, configPath: Config.filePath,
                controlCenterOpen: GlobalStates.controlPanelOpen,
                doNotDisturb: Notifications.silent, notificationPopups: Notifications.popupList.length,
                controlCenterActions: Array.from(Config.options.hpos.controlCenter.actions),
                reducedMotion: HposTokens.reducedMotion, reducedTransparency: HposTokens.reducedTransparency})
        }
    }
    LazyLoader {
        active: root.preferencesOpen
        component: FloatingWindow {
            title: "HP-OS"
            implicitWidth: 880; implicitHeight: 680
            color: HposTokens.canvas
            onVisibleChanged: if (!visible) root.preferencesOpen = false
            HposPreferences { anchors.fill: parent; anchors.margins: 24 }
        }
    }
    LazyLoader {
        active: root.galleryOpen
        component: FloatingWindow {
            title: "HP-OS · Component Gallery"
            implicitWidth: 960; implicitHeight: 760
            color: HposTokens.canvas
            onVisibleChanged: if (!visible) root.galleryOpen = false
            HposGallery { anchors.fill: parent; anchors.margins: 24 }
        }
    }
}
