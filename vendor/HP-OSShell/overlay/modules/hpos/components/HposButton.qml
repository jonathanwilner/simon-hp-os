import QtQuick
import QtQuick.Controls
import qs.modules.hpos.design
Button {
    id: root
    property bool emphasized: false
    implicitHeight: HposTokens.touchTarget
    implicitWidth: Math.max(implicitContentWidth + 32, HposTokens.touchTarget)
    font.family: HposTokens.fontFamily
    font.pixelSize: HposTokens.body
    focusPolicy: Qt.StrongFocus
    Accessible.name: text
    contentItem: Text {
        font.family: HposTokens.fontFamily
        font.pixelSize: HposTokens.body
        text: root.text
        color: root.emphasized ? HposTokens.onAccent : HposTokens.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: HposTokens.radiusSmall
        color: root.emphasized ? HposTokens.accent : HposTokens.elevated
        opacity: root.enabled ? (root.down ? 0.72 : root.hovered ? 0.86 : 1) : 0.4
        border.width: root.visualFocus ? 2 : 0
        border.color: HposTokens.focus
        Behavior on opacity { NumberAnimation { duration: HposTokens.feedbackDuration } }
    }
    scale: down && !HposTokens.reducedMotion ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: HposTokens.feedbackDuration } }
}
