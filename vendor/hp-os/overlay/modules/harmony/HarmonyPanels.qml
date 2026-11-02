import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.services
import qs.modules.common
import qs.modules.harmony.design
import qs.modules.harmony.settings
import qs.modules.harmony.launcher

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
        const p = Config.options.harmony
        if (p.schemaVersion < 1) Config.setNestedValue("harmony.schemaVersion", 1)
        // Future versions are left untouched so a downgrade does not destroy preferences.
        if (p.schemaVersion > 1) return
        for (const item of [ ["appearance", ["auto", "light", "dark"], "auto"],
                ["quality", ["full", "balanced", "performance"], "balanced"],
                ["locale", ["auto", "en_US", "zh_CN"], "auto"] ]) {
            if (!item[1].includes(p[item[0]])) Config.setNestedValue("harmony." + item[0], item[2])
        }
        if (!Number.isFinite(p.materialIntensity) || p.materialIntensity < 0.5 || p.materialIntensity > 1.5)
            Config.setNestedValue("harmony.materialIntensity", 1.0)
    }
    LazyLoader {
        active: (root.applicationCenterLoaded || GlobalStates.searchOpen) && Config.options.harmony.applicationCenter
        component: HarmonyApplicationCenter {}
    }
    LazyLoader {
        active: true // Keep native layer surfaces alive across Start toggles.
        component: HarmonyStartMenu { onSettingsRequested: root.preferencesOpen = true }
    }
    Component.onCompleted: { validatePreferences(); HarmonyStartState.observe() }
    IpcHandler {
        target: "harmony"
        function start(): void { HarmonyStartState.toggle() }
        function settings(): void { root.preferencesOpen = true }
        function gallery(): void { root.galleryOpen = true }
        function close(): void { HarmonyStartState.opened = false; root.galleryOpen = false; root.preferencesOpen = false }
        function keyboard(): void { touchCommand.command = ["touch-support", "toggle"]; touchCommand.running = true }
        function touchSettings(): void { touchCommand.command = ["touch-support", "settings"]; touchCommand.running = true }
        function controlCenter(): void { GlobalStates.controlPanelOpen = !GlobalStates.controlPanelOpen }
        function notifications(): void { GlobalStates.sidebarRightOpen = !GlobalStates.sidebarRightOpen }
        function set(key: string, value: string): bool {
            let parsed = value
            try { parsed = JSON.parse(value) } catch (_) {}
            return HarmonyTokens.setPreference(key, parsed)
        }
        function status(): string {
            return JSON.stringify({applicationCenterOpen: GlobalStates.searchOpen, startOpen: HarmonyStartState.opened, recentFiles: HarmonyStartState.files.length, recentApps: HarmonyStartState.apps.length, family: Config.options.panelFamily, font: HarmonyTokens.fontFamily,
                genuineFont: HarmonyTokens.genuineFontAvailable, dark: HarmonyTokens.dark,
                quality: HarmonyTokens.quality, locale: HarmonyTokens.preferences.locale, notificationCount: Notifications.list.length,
                audioReady: Audio.ready, configPath: Config.filePath,
                controlCenterOpen: GlobalStates.controlPanelOpen,
                doNotDisturb: Notifications.silent, notificationPopups: Notifications.popupList.length,
                controlCenterActions: Array.from(Config.options.harmony.controlCenter.actions),
                reducedMotion: HarmonyTokens.reducedMotion, reducedTransparency: HarmonyTokens.reducedTransparency})
        }
    }
    LazyLoader {
        active: root.preferencesOpen
        component: FloatingWindow {
            title: "HP-OS"
            implicitWidth: 880; implicitHeight: 680
            color: HarmonyTokens.canvas
            onVisibleChanged: if (!visible) root.preferencesOpen = false
            HarmonyPreferences { anchors.fill: parent; anchors.margins: 24 }
        }
    }
    LazyLoader {
        active: root.galleryOpen
        component: FloatingWindow {
            title: "HP-OS · Component Gallery"
            implicitWidth: 960; implicitHeight: 760
            color: HarmonyTokens.canvas
            onVisibleChanged: if (!visible) root.galleryOpen = false
            HarmonyGallery { anchors.fill: parent; anchors.margins: 24 }
        }
    }
}
