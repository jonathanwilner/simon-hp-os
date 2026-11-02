import QtQuick
QtObject {
    property bool dark: false
    property bool reducedMotion: false
    property real scale: 1
    property color accent: dark ? "#83baff" : "#0a59f7"
    readonly property color canvas: dark ? "#202226" : "#e5e7eb"
    readonly property color key: dark ? "#41444b" : "#ffffff"
    readonly property color modifier: dark ? "#30333a" : "#c4c8d0"
    readonly property color pressed: dark ? "#647084" : "#c5d9fc"
    readonly property color text: dark ? "#f2f3f5" : "#19202a"
    readonly property color secondary: dark ? "#b9bdc6" : "#616975"
    readonly property color shadow: dark ? "#17191d" : "#a8adb6"
    readonly property color onAccent: dark ? "#102c50" : "#ffffff"
    readonly property string font: "Noto Sans"
    readonly property int gap: Math.round(7 * scale)
    readonly property int radius: Math.round(10 * scale)
    readonly property int inset: Math.round(10 * scale)
    readonly property int feedbackDuration: reducedMotion ? 0 : 70
    readonly property int revealDuration: reducedMotion ? 0 : 180
}
