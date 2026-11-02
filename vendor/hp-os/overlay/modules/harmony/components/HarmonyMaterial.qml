import QtQuick
import QtQuick.Effects
import qs.modules.harmony.design

Rectangle {
    id: root
    property string thickness: "REGULAR"
    property bool interactive: false
    // The compositor owns background blur. This item paints tint and highlights only.
    property bool compositorBlur: false
    readonly property var recipe: HarmonyTokens.recipe(thickness)
    color: compositorBlur ? HarmonyTokens.tint(thickness) : HarmonyTokens.surface
    radius: HarmonyTokens.radiusPanel
    border.width: 1
    border.color: HarmonyTokens.outline
    antialiasing: true
    RectangularShadow {
        anchors.fill: parent
        z: -1
        visible: HarmonyTokens.quality !== "performance"
        radius: root.radius
        blur: root.recipe.elevation * 2
        offset.y: root.recipe.elevation / 3
        color: HarmonyTokens.dark ? "#50000000" : "#180b203d"
    }
    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        color: "transparent"
        border.width: hover.hovered && root.interactive ? 2 : 1
        border.color: hover.hovered && root.interactive ? "#60ffffff" : "#20ffffff"
        Behavior on border.color { ColorAnimation { duration: HarmonyTokens.feedbackDuration } }
    }
    HoverHandler { id: hover; enabled: root.interactive }
}
