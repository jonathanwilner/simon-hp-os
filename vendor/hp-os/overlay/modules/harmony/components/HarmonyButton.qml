import QtQuick
import QtQuick.Controls
import qs.modules.harmony.design
Button {
    id: root
    property bool emphasized: false
    implicitHeight: HarmonyTokens.touchTarget
    implicitWidth: Math.max(implicitContentWidth + 32, HarmonyTokens.touchTarget)
    font.family: HarmonyTokens.fontFamily
    font.pixelSize: HarmonyTokens.body
    focusPolicy: Qt.StrongFocus
    Accessible.name: text
    contentItem: Text {
        font.family: HarmonyTokens.fontFamily
        font.pixelSize: HarmonyTokens.body
        text: root.text
        color: root.emphasized ? HarmonyTokens.onAccent : HarmonyTokens.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: HarmonyTokens.radiusSmall
        color: root.emphasized ? HarmonyTokens.accent : HarmonyTokens.elevated
        opacity: root.enabled ? (root.down ? 0.72 : root.hovered ? 0.86 : 1) : 0.4
        border.width: root.visualFocus ? 2 : 0
        border.color: HarmonyTokens.focus
        Behavior on opacity { NumberAnimation { duration: HarmonyTokens.feedbackDuration } }
    }
    scale: down && !HarmonyTokens.reducedMotion ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: HarmonyTokens.feedbackDuration } }
}
