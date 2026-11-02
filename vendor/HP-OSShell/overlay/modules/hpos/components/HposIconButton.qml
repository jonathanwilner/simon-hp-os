import QtQuick
import QtQuick.Controls
HposButton {
    // Use a supplied icon and an accessible text label; glyphs are not fake service state.
    display: AbstractButton.IconOnly
    contentItem: Image { source: parent.icon.source; sourceSize.width: 24; sourceSize.height: 24; fillMode: Image.PreserveAspectFit }
}
