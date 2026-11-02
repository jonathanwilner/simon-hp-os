import QtQuick
import QtQuick.Controls
import qs.modules.hpos.design
Button {
    id: root
    // Controlled component: user intent never replaces confirmed service state.
    property bool confirmed: false
    signal requested(bool value)
    onClicked: root.requested(!root.confirmed)
    background: Item {}
    implicitHeight: HposTokens.touchTarget
    font.family: HposTokens.fontFamily
    font.pixelSize: HposTokens.body
    Accessible.name: text
    indicator: Rectangle {
        x: root.leftPadding; y: (root.height - height) / 2
        width: 44; height: 26; radius: 13
        color: root.confirmed ? HposTokens.accent : HposTokens.secondary
        opacity: root.enabled ? 1 : 0.4
        border.width: root.visualFocus ? 2 : 0
        border.color: HposTokens.focus
        Rectangle {
            width: 22; height: 22; radius: 11; y: 2
            x: root.confirmed ? 20 : 2
            color: "white"
            Behavior on x { NumberAnimation { duration: HposTokens.feedbackDuration } }
        }
    }
    contentItem: HposText {
        text: root.text
        leftPadding: root.indicator.width + root.spacing
        verticalAlignment: Text.AlignVCenter
    }
}
