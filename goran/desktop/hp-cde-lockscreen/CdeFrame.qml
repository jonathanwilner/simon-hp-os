import QtQuick

// Decorative only: no focus, input handlers, authentication, or session state.
Rectangle {
    id: frame
    property int bevelWidth: 2
    property bool sunken: false
    property bool nvidiaGreen: false
    color: nvidiaGreen ? "#c6dda4" : "#b5c4d5"
    radius: 0
    Rectangle { anchors.top: parent.top; width: parent.width; height: frame.bevelWidth; color: frame.sunken ? (frame.nvidiaGreen ? "#527d00" : "#72849a") : (frame.nvidiaGreen ? "#eff8e1" : "#e4eaf1") }
    Rectangle { anchors.left: parent.left; width: frame.bevelWidth; height: parent.height; color: frame.sunken ? (frame.nvidiaGreen ? "#527d00" : "#72849a") : (frame.nvidiaGreen ? "#eff8e1" : "#e4eaf1") }
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: frame.bevelWidth; color: frame.sunken ? (frame.nvidiaGreen ? "#eff8e1" : "#e4eaf1") : (frame.nvidiaGreen ? "#527d00" : "#72849a") }
    Rectangle { anchors.right: parent.right; width: frame.bevelWidth; height: parent.height; color: frame.sunken ? (frame.nvidiaGreen ? "#eff8e1" : "#e4eaf1") : (frame.nvidiaGreen ? "#527d00" : "#72849a") }
}
