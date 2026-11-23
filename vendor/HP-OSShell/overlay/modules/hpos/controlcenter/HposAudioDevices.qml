pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell.Services.Pipewire
import qs.services
import qs.modules.hpos.components
import qs.modules.hpos.design
import qs.modules.iris.components
import qs.modules.iris.style

ColumnLayout {
    id: root

    required property var outputName
    readonly property real d: IrisStyle.density
    spacing: 8 * root.d

    IrisText {
        text: HposTokens.tr("Output devices", "输出设备")
        role: IrisText.Meta
        font.weight: Font.DemiBold
    }
    IrisText {
        visible: Audio.outputDevices.length === 0
        text: HposTokens.tr("No audio outputs available", "无可用的音频输出")
        color: IrisStyle.subtext
    }

    function isVirtual(node): bool {
        const props = node.properties ?? {}
        return String(props["node.virtual"]) === "true"
            || props["factory.name"] === "support.null-audio-sink"
    }

    Repeater {
        model: Array.from(Audio.outputDevices).sort((a, b) =>
            Number(root.isVirtual(a)) - Number(root.isVirtual(b)))

        delegate: ColumnLayout {
            id: device

            required property PwNode modelData
            readonly property string deviceName: root.outputName(modelData)
            readonly property bool isDefault: Audio.rawSink === modelData
            readonly property bool isVirtual: root.isVirtual(modelData)
            readonly property bool muted: modelData.audio?.muted ?? false
            readonly property real volume: modelData.audio?.volume ?? 0

            Layout.fillWidth: true
            spacing: 2 * root.d

            PwObjectTracker { objects: [device.modelData] }

            IrisText {
                Layout.fillWidth: true
                text: device.isVirtual
                    ? HposTokens.tr("%1 (virtual)", "%1（虚拟）").arg(device.deviceName)
                    : device.deviceName
                font.weight: Font.DemiBold
                wrapMode: Text.WrapAnywhere
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8 * root.d

                IrisIconButton {
                    materialIcon: device.muted ? "volume_off" : "volume_up"
                    enabled: Boolean(device.modelData.audio)
                    Accessible.name: (device.muted
                        ? HposTokens.tr("Unmute %1", "取消静音 %1")
                        : HposTokens.tr("Mute %1", "静音 %1")).arg(device.deviceName)
                    onClicked: device.modelData.audio.muted = !device.muted
                }
                HposSlider {
                    id: slider
                    Layout.fillWidth: true
                    enabled: Boolean(device.modelData.audio)
                    to: Math.min(1, Audio.ceiling)
                    stepSize: 0.01
                    Accessible.name: HposTokens.tr("%1 volume", "%1 音量").arg(device.deviceName)
                    Binding on value {
                        value: Math.min(slider.to, device.volume)
                        when: !slider.pressed
                        restoreMode: Binding.RestoreNone
                    }
                    onMoved: if (device.modelData.audio) device.modelData.audio.volume = value
                }
                IrisText {
                    text: Math.round((slider.pressed ? slider.value : device.volume) * 100) + "%"
                    color: device.muted ? IrisStyle.subtext : IrisStyle.text
                    horizontalAlignment: Text.AlignRight
                    Layout.minimumWidth: 38 * root.d
                }
                IrisButton {
                    text: device.isDefault
                        ? HposTokens.tr("Default", "默认")
                        : HposTokens.tr("Set default", "设为默认")
                    enabled: !device.isDefault
                    selected: device.isDefault
                    Accessible.name: HposTokens.tr("Set %1 as default output", "将 %1 设为默认输出").arg(device.deviceName)
                    onClicked: Pipewire.preferredDefaultAudioSink = device.modelData
                }
            }
        }
    }

    IrisText {
        visible: Audio.inputDevices.length > 0
        text: HposTokens.tr("Input devices", "输入设备")
        role: IrisText.Meta
        font.weight: Font.DemiBold
    }
    IrisDeviceList {
        Layout.fillWidth: true
        outputs: false
    }
}
