import QtQuick
import Quickshell
ShellRoot {
    KeyboardController { id:inputController; settingsOnly:true }
    FloatingWindow {
        visible:true; title:"Touch & Keyboard"; implicitWidth:520; implicitHeight:480; color:theme.canvas
        KeyboardTokens { id:theme; dark:inputController.prefs.colorScheme==="dark" || (inputController.prefs.colorScheme!=="light" && inputController.systemDark) }
        KeyboardSettings { anchors.fill:parent; anchors.margins:24; controller:inputController; tokens:theme }
    }
}
