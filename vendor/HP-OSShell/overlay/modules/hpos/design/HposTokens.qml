pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import qs.modules.common

QtObject {
    id: root
    readonly property bool active: Config.options?.panelFamily === "hpos"
    readonly property var preferences: Config.options?.hpos ?? ({})
    readonly property bool dark: preferences.appearance === "dark" ||
        (preferences.appearance !== "light" && Appearance.m3colors.darkmode)
    // Publish the effective mode on startup and every change, including Auto.
    property Timer applicationThemeDebounce: Timer {
        interval: 100
        onTriggered: {
            if (root.active && Config.ready && Quickshell.env("INIR_SAFE_PREVIEW") !== "1"
                    && Quickshell.env("INIR_STANDALONE_WINDOW") !== "1" && !applicationThemeProcess.running) {
                applicationThemeProcess.command = ["hp-os-appearance", root.dark ? "dark" : "light"]
                applicationThemeProcess.running = true
            }
        }
    }
    property Process applicationThemeProcess: Process {
        onExited: (code, status) => {
            if (code !== 0) console.warn("[HP-OS] Could not publish application appearance", code)
            if (command[1] !== (root.dark ? "dark" : "light")) applicationThemeDebounce.restart()
        }
    }
    property Connections applicationThemeConfig: Connections {
        target: Config
        function onReadyChanged() { applicationThemeDebounce.restart() }
    }
    onDarkChanged: applicationThemeDebounce.restart()
    onActiveChanged: applicationThemeDebounce.restart()
    readonly property bool reducedMotion: preferences.reducedMotion ?? false
    readonly property bool reducedTransparency: (preferences.reducedTransparency ?? false) || quality === "performance"
    readonly property string quality: ["full", "balanced", "performance"].includes(preferences.quality) ? preferences.quality : "balanced"
    readonly property real scale: Math.max(0.75, Math.min(2, Appearance.fontSizeScale ?? 1))
    readonly property bool chinese: String(preferences.locale === "auto" ? Qt.locale().name : preferences.locale).startsWith("zh")
    readonly property var families: Qt.fontFamilies()
    readonly property string requestedFont: preferences.fontFamily || (chinese ? "HarmonyOS Sans SC" : "HarmonyOS Sans")
    readonly property bool genuineFontAvailable: families.includes(requestedFont)
    // A visible fallback is deliberate: installation checks enforce genuine fonts for acceptance.
    readonly property string fontFamily: genuineFontAvailable ? requestedFont : "sans-serif"
    readonly property string fontStatus: genuineFontAvailable ? requestedFont : "HarmonyOS Sans missing · explicit system fallback"
    readonly property color canvas: dark ? "#121316" : "#f1f3f5"
    readonly property color surface: dark ? "#242528" : "#ffffff"
    readonly property color elevated: dark ? "#303136" : "#fafbfc"
    readonly property color text: dark ? "#f1f3f5" : "#18212b"
    readonly property color secondary: dark ? "#b5bac2" : "#596573"
    readonly property color accent: dark ? "#83baff" : "#0a59f7"
    readonly property color onAccent: dark ? "#102c50" : "#ffffff"
    readonly property color outline: dark ? "#30ffffff" : "#30ffffff"
    readonly property color focus: dark ? "#a2caff" : "#004fc4"
    readonly property int space: Math.round(8 * scale)
    readonly property int radiusSmall: Math.round(12 * scale)
    readonly property int radiusCard: Math.round(20 * scale)
    readonly property int radiusPanel: Math.round(28 * scale)
    readonly property int touchTarget: Math.round(44 * scale)
    readonly property int caption: Math.round(12 * scale)
    readonly property int body: Math.round(14 * scale)
    readonly property int title: Math.round(22 * scale)
    readonly property int display: Math.round(36 * scale)
    readonly property int feedbackDuration: reducedMotion ? 0 : 120
    readonly property int revealDuration: reducedMotion ? 0 : 260
    readonly property var motionCurve: [0.2, 0.0, 0.2, 1.0, 1.0, 1.0]
    readonly property var materialNames: ["ULTRA_THIN", "THIN", "REGULAR", "THICK", "ULTRA_THICK"]
    // Material names follow the reference design; these numeric recipes are Linux visual approximations.
    readonly property var materials: ({
        ULTRA_THIN: { opacity: 0.48, blur: 16, saturation: 1.20, elevation: 6 },
        THIN: { opacity: 0.62, blur: 24, saturation: 1.16, elevation: 10 },
        REGULAR: { opacity: 0.76, blur: 32, saturation: 1.12, elevation: 16 },
        THICK: { opacity: 0.88, blur: 40, saturation: 1.08, elevation: 22 },
        ULTRA_THICK: { opacity: 0.96, blur: 48, saturation: 1.04, elevation: 28 }
    })
    function recipe(name) { return materials[name] ?? materials.REGULAR }
    function tint(name) {
        const alpha = reducedTransparency ? 1 : Math.min(1, recipe(name).opacity * Math.max(0.5, Math.min(1.5, preferences.materialIntensity ?? 1)))
        return Qt.rgba(surface.r, surface.g, surface.b, alpha)
    }
    function tr(english, zh) { return chinese ? zh : english }
    function setPreference(key, value) {
        const enums = { appearance: ["auto", "light", "dark"], quality: ["full", "balanced", "performance"], locale: ["auto", "en_US", "zh_CN"] }
        if (enums[key] && !enums[key].includes(value)) return false
        if (["reducedMotion", "reducedTransparency"].includes(key) && typeof value !== "boolean") return false
        if (key === "materialIntensity" && (!Number.isFinite(value) || value < 0.5 || value > 1.5)) return false
        if (!["appearance", "quality", "locale", "reducedMotion", "reducedTransparency", "materialIntensity", "fontFamily"].includes(key)) return false
        Config.setNestedValue("hpos." + key, value)
        if (key === "locale") Config.setNestedValue("language.ui", value)
        return true
    }
    Component.onCompleted: { applicationThemeDebounce.restart(); if (active && !genuineFontAvailable) console.warn("[HP-OS] " + fontStatus) }
}
