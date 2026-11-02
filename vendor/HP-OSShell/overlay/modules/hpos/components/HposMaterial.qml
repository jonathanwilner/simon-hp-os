import QtQuick
import QtQuick.Effects
import qs.modules.hpos.design

Rectangle {
    id: root
    property string thickness: "REGULAR"
    property bool interactive: false
    // The compositor owns background blur. This item paints tint and highlights only.
    property bool compositorBlur: false
    readonly property var recipe: HposTokens.recipe(thickness)
    color: compositorBlur ? HposTokens.tint(thickness) : HposTokens.surface
    radius: HposTokens.radiusPanel
    border.width: 1
    border.color: HposTokens.outline
    antialiasing: true
    RectangularShadow {
        anchors.fill: parent
        z: -1
        visible: HposTokens.quality !== "performance"
        radius: root.radius
        blur: root.recipe.elevation * 2
        offset.y: root.recipe.elevation / 3
        color: HposTokens.dark ? "#50000000" : "#180b203d"
    }
    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        color: "transparent"
        border.width: hover.hovered && root.interactive ? 2 : 1
        border.color: hover.hovered && root.interactive ? "#60ffffff" : "#20ffffff"
        Behavior on border.color { ColorAnimation { duration: HposTokens.feedbackDuration } }
    }
    HoverHandler { id: hover; enabled: root.interactive }
}
