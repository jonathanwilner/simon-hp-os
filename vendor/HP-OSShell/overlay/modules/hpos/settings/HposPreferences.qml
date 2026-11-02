import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs
import qs.modules.common
import qs.modules.hpos.design
import qs.modules.hpos.components

ScrollView {
    id: root
    Process { id: touchSettings; command: ["touch-support", "settings"] }
    contentWidth: availableWidth
    ColumnLayout {
        width: root.availableWidth
        spacing: 20
        HposText { text: "HP-OS"; role: "display" }
        HposText { text: "Based on iNiR by snowarch (https://github.com/snowarch/inir)"; role: "secondary"; Layout.fillWidth: true }
        HposButton {
            text: HposTokens.tr("Touch & Keyboard", "触控与键盘")
            onClicked: touchSettings.running = true
        }
        HposText { text: HposTokens.tr("Personalization", "个性化"); role: "title" }
        HposText { text: HposTokens.tr("Appearance", "外观") }
        HposSegmentedControl {
            selected: HposTokens.preferences.appearance
            choices: [{value:"auto",label:HposTokens.tr("Automatic", "自动")}, {value:"light",label:HposTokens.tr("Light", "浅色")}, {value:"dark",label:HposTokens.tr("Dark", "深色")}]
            onSelectedValue: value => HposTokens.setPreference("appearance", value)
        }
        HposText { text: HposTokens.tr("Material quality", "材质质量") }
        HposSegmentedControl {
            selected: HposTokens.quality
            choices: [{value:"full",label:HposTokens.tr("Full", "完整")}, {value:"balanced",label:HposTokens.tr("Balanced", "均衡")}, {value:"performance",label:HposTokens.tr("Performance", "性能")}]
            onSelectedValue: value => HposTokens.setPreference("quality", value)
        }
        HposToggle {
            text: HposTokens.tr("Reduce motion", "减弱动态效果")
            confirmed: HposTokens.reducedMotion
            onRequested: value => HposTokens.setPreference("reducedMotion", value)
        }
        HposToggle {
            text: HposTokens.tr("Reduce transparency", "降低透明度")
            confirmed: HposTokens.preferences.reducedTransparency
            onRequested: value => HposTokens.setPreference("reducedTransparency", value)
        }
        HposText { text: HposTokens.tr("Material intensity", "材质强度") }
        HposSlider {
            from: 0.5; to: 1.5; stepSize: 0.05
            value: HposTokens.preferences.materialIntensity
            Accessible.name: HposTokens.tr("Material intensity", "材质强度")
            onMoved: HposTokens.setPreference("materialIntensity", value)
        }
        HposToggle {
            text: HposTokens.tr("Application grid (disable for advanced search)", "应用网格（关闭后使用高级搜索）")
            confirmed: Config.options.hpos.applicationCenter
            onRequested: value => Config.setNestedValue("hpos.applicationCenter", value)
        }
        HposText { text: HposTokens.tr("Language", "语言") }
        HposSegmentedControl {
            selected: HposTokens.preferences.locale
            choices: [{value:"auto",label:HposTokens.tr("System", "系统")}, {value:"en_US",label:"English"}, {value:"zh_CN",label:"简体中文"}]
            onSelectedValue: value => {
                HposTokens.setPreference("locale", value)
                Config.setNestedValue("language.ui", value)
            }
        }
        HposText { text: HposTokens.fontStatus; role: "secondary" }
        HposText {
            Layout.fillWidth: true
            text: HposTokens.tr("Desktop, dock, applications, network, sound, displays, shortcuts, lock screen and service cards use the shared iNiR settings.", "桌面、程序坞、应用、网络、声音、显示、快捷键、锁屏和服务卡片使用共享 iNiR 设置。")
        }
        HposButton {
            text: HposTokens.tr("Open all settings", "打开全部设置"); emphasized: true
            onClicked: GlobalStates.openSettings()
        }
        HposText {
            Layout.fillWidth: true; role: "secondary"
            text: HposTokens.tr("HP-OS is an independent Linux desktop based on iNiR, with mobile-inspired controls and navigation.", "HP-OS 是基于 iNiR 的独立 Linux 桌面，采用移动设备风格的控件和导航。")
        }
    }
}
