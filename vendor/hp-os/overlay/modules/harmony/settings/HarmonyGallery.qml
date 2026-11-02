import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.services
import qs.modules.harmony.design
import qs.modules.harmony.components
ScrollView {
    id: root
    contentWidth: availableWidth
    ColumnLayout {
        width: root.availableWidth; spacing: 24
        HarmonyText { text: "HP-OS · 沉浸光感"; role: "display" }
        HarmonyText { text: "Live components · Numeric material recipes are visual approximations"; role: "secondary" }
        RowLayout {
            Repeater {
                model: HarmonyTokens.materialNames
                HarmonyMaterial {
                    required property string modelData
                    Layout.fillWidth: true; Layout.preferredHeight: 130
                    thickness: modelData; interactive: true
                    HarmonyText { anchors.centerIn: parent; text: parent.modelData; font.pixelSize: 11 }
                }
            }
        }
        HarmonyText { text: "HarmonyOS Sans · 简体中文 · 0123456789"; role: "title" }
        HarmonyText { text: HarmonyTokens.fontStatus; role: "secondary" }
        RowLayout {
            HarmonyButton { text: "Primary / 主要"; emphasized: true }
            HarmonyButton { text: "Standard / 标准" }
            HarmonyButton { text: "Unavailable / 不可用"; enabled: false }
        }
        HarmonyToggle {
            text: "Do Not Disturb / 免打扰"
            confirmed: Notifications.silent
            onRequested: value => { if (value !== Notifications.silent) Notifications.toggleSilent() }
        }
        HarmonyText { text: Audio.ready ? "Live output volume / 音量" : "Audio service unavailable / 音频服务不可用" }
        HarmonySlider {
            enabled: Audio.ready
            value: Audio.value; from: 0; to: 1
            Accessible.name: "Output volume"
            onMoved: Audio.setSinkVolume(value)
        }
        HarmonySegmentedControl {
            selected: HarmonyTokens.preferences.appearance
            choices: [{value:"light",label:"Light / 浅色"},{value:"dark",label:"Dark / 深色"},{value:"auto",label:"Auto / 自动"}]
            onSelectedValue: value => HarmonyTokens.setPreference("appearance", value)
        }
    }
}
