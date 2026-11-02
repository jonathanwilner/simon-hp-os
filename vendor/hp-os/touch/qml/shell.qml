import QtQuick
import Quickshell
ShellRoot {
    KeyboardController { id:inputController }
    LazyLoader { active:!inputController.settingsOnly; HpOsKeyboard { controller:inputController } }
    LazyLoader {
        active:inputController.settingsOnly
        FloatingWindow {
            visible:true; title:"Touch & Keyboard"; implicitWidth:520; implicitHeight:420; color:settingsTokens.canvas
            KeyboardTokens { id:settingsTokens; dark:inputController.prefs.colorScheme==="dark" || (inputController.prefs.colorScheme!=="light" && inputController.systemDark) }
            KeyboardSettings { anchors.fill:parent; anchors.margins:24; controller:inputController; tokens:settingsTokens }
        }
    }
}
