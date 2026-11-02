import QtQuick
import QtQuick.Layouts
import qs.modules.harmony.design
RowLayout {
    id: root
    property var choices: []
    property string selected: ""
    signal selectedValue(string value)
    spacing: 4
    Repeater {
        model: root.choices
        HarmonyButton {
            required property var modelData
            text: modelData.label
            emphasized: root.selected === modelData.value
            onClicked: root.selectedValue(modelData.value)
        }
    }
}
