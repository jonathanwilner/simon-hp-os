import QtQuick
import QtQuick.Controls
import qs.modules.harmony.design
Slider {
    id: root
    implicitHeight: HarmonyTokens.touchTarget
    implicitWidth: 240
    Accessible.name: "Value"
    background: Rectangle {
        x: root.leftPadding; y: (root.height - height) / 2
        width: root.availableWidth; height: 8; radius: 4
        color: HarmonyTokens.secondary
        Rectangle { width: root.visualPosition * parent.width; height: parent.height; radius: 4; color: HarmonyTokens.accent }
    }
    handle: Rectangle {
        x: root.leftPadding + root.visualPosition * (root.availableWidth - width)
        y: (root.height - height) / 2
        width: 24; height: 24; radius: 12
        color: HarmonyTokens.surface
        border.width: root.visualFocus ? 3 : 1
        border.color: HarmonyTokens.accent
    }
}
