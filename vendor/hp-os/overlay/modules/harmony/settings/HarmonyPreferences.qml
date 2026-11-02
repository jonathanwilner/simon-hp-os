import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs
import qs.modules.common
import qs.modules.harmony.design
import qs.modules.harmony.components

ScrollView {
    id: root
    Process { id: touchSettings; command: ["touch-support", "settings"] }
    contentWidth: availableWidth
    ColumnLayout {
        width: root.availableWidth
        spacing: 20
        HarmonyText { text: "HP-OS"; role: "display" }
        HarmonyText { text: "Based on iNiR by snowarch (https://github.com/snowarch/inir)"; role: "secondary"; Layout.fillWidth: true }
        HarmonyButton {
            text: HarmonyTokens.tr("Touch & Keyboard", "触控与键盘")
            onClicked: touchSettings.running = true
        }
        HarmonyText { text: HarmonyTokens.tr("Personalization", "个性化"); role: "title" }
        HarmonyText { text: HarmonyTokens.tr("Appearance", "外观") }
        HarmonySegmentedControl {
            selected: HarmonyTokens.preferences.appearance
            choices: [{value:"auto",label:HarmonyTokens.tr("Automatic", "自动")}, {value:"light",label:HarmonyTokens.tr("Light", "浅色")}, {value:"dark",label:HarmonyTokens.tr("Dark", "深色")}]
            onSelectedValue: value => HarmonyTokens.setPreference("appearance", value)
        }
        HarmonyText { text: HarmonyTokens.tr("Material quality", "材质质量") }
        HarmonySegmentedControl {
            selected: HarmonyTokens.quality
            choices: [{value:"full",label:HarmonyTokens.tr("Full", "完整")}, {value:"balanced",label:HarmonyTokens.tr("Balanced", "均衡")}, {value:"performance",label:HarmonyTokens.tr("Performance", "性能")}]
            onSelectedValue: value => HarmonyTokens.setPreference("quality", value)
        }
        HarmonyToggle {
            text: HarmonyTokens.tr("Reduce motion", "减弱动态效果")
            confirmed: HarmonyTokens.reducedMotion
            onRequested: value => HarmonyTokens.setPreference("reducedMotion", value)
        }
        HarmonyToggle {
            text: HarmonyTokens.tr("Reduce transparency", "降低透明度")
            confirmed: HarmonyTokens.preferences.reducedTransparency
            onRequested: value => HarmonyTokens.setPreference("reducedTransparency", value)
        }
        HarmonyText { text: HarmonyTokens.tr("Material intensity", "材质强度") }
        HarmonySlider {
            from: 0.5; to: 1.5; stepSize: 0.05
            value: HarmonyTokens.preferences.materialIntensity
            Accessible.name: HarmonyTokens.tr("Material intensity", "材质强度")
            onMoved: HarmonyTokens.setPreference("materialIntensity", value)
        }
        HarmonyToggle {
            text: HarmonyTokens.tr("Application grid (disable for advanced search)", "应用网格（关闭后使用高级搜索）")
            confirmed: Config.options.harmony.applicationCenter
            onRequested: value => Config.setNestedValue("harmony.applicationCenter", value)
        }
        HarmonyText { text: HarmonyTokens.tr("Language", "语言") }
        HarmonySegmentedControl {
            selected: HarmonyTokens.preferences.locale
            choices: [{value:"auto",label:HarmonyTokens.tr("System", "系统")}, {value:"en_US",label:"English"}, {value:"zh_CN",label:"简体中文"}]
            onSelectedValue: value => {
                HarmonyTokens.setPreference("locale", value)
                Config.setNestedValue("language.ui", value)
            }
        }
        HarmonyText { text: HarmonyTokens.fontStatus; role: "secondary" }
        HarmonyText {
            Layout.fillWidth: true
            text: HarmonyTokens.tr("Desktop, dock, applications, network, sound, displays, shortcuts, lock screen and service cards use the shared iNiR settings.", "桌面、程序坞、应用、网络、声音、显示、快捷键、锁屏和服务卡片使用共享 iNiR 设置。")
        }
        HarmonyButton {
            text: HarmonyTokens.tr("Open all settings", "打开全部设置"); emphasized: true
            onClicked: GlobalStates.openSettings()
        }
        HarmonyText {
            Layout.fillWidth: true; role: "secondary"
            text: HarmonyTokens.tr("HP-OS is an independent Linux desktop based on iNiR, with mobile-inspired controls and navigation.", "HP-OS 是基于 iNiR 的独立 Linux 桌面，采用移动设备风格的控件和导航。")
        }
    }
}
