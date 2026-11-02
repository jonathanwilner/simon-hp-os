import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.services
import qs.modules.hpos.design
import qs.modules.hpos.components
ScrollView {
    id: root
    contentWidth: availableWidth
    ColumnLayout {
        width: root.availableWidth; spacing: 24
        HposText { text: "HP-OS · 沉浸光感"; role: "display" }
        HposText { text: "Live components · Numeric material recipes are visual approximations"; role: "secondary" }
        RowLayout {
            Repeater {
                model: HposTokens.materialNames
                HposMaterial {
                    required property string modelData
                    Layout.fillWidth: true; Layout.preferredHeight: 130
                    thickness: modelData; interactive: true
                    HposText { anchors.centerIn: parent; text: parent.modelData; font.pixelSize: 11 }
                }
            }
        }
        HposText { text: "HarmonyOS Sans · 简体中文 · 0123456789"; role: "title" }
        HposText { text: HposTokens.fontStatus; role: "secondary" }
        RowLayout {
            HposButton { text: "Primary / 主要"; emphasized: true }
            HposButton { text: "Standard / 标准" }
            HposButton { text: "Unavailable / 不可用"; enabled: false }
        }
        HposToggle {
            text: "Do Not Disturb / 免打扰"
            confirmed: Notifications.silent
            onRequested: value => { if (value !== Notifications.silent) Notifications.toggleSilent() }
        }
        HposText { text: Audio.ready ? "Live output volume / 音量" : "Audio service unavailable / 音频服务不可用" }
        HposSlider {
            enabled: Audio.ready
            value: Audio.value; from: 0; to: 1
            Accessible.name: "Output volume"
            onMoved: Audio.setSinkVolume(value)
        }
        HposSegmentedControl {
            selected: HposTokens.preferences.appearance
            choices: [{value:"light",label:"Light / 浅色"},{value:"dark",label:"Dark / 深色"},{value:"auto",label:"Auto / 自动"}]
            onSelectedValue: value => HposTokens.setPreference("appearance", value)
        }
    }
}
