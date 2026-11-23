"""Add independent output controls to the DMS and Dux control centers."""

import re
import sys
from pathlib import Path

CONTROL_CENTER = Path("Modules/ControlCenter")
DETAIL = CONTROL_CENTER / "Details/AudioOutputDetail.qml"
SLIDER = CONTROL_CENTER / "Widgets/AudioSliderRow.qml"
TILE = CONTROL_CENTER / "Widgets/AudioDeviceTile.qml"
GRID = CONTROL_CENTER / "Components/DragDropGrid.qml"
SERVICE = Path("Services/AudioService.qml")
MARKER = "// Fleet per-device audio controls."

OUTPUT_NAME = '''    function outputDisplayName(node) {
        const alias = getDeviceAlias(node?.name);
        if (alias)
            return alias;
        switch (node?.name) {
        case "sink-sunshine-stereo":
            return I18n.tr("Sunshine Stereo");
        case "sink-sunshine-surround51":
            return I18n.tr("Sunshine Surround 5.1");
        case "sink-sunshine-surround71":
            return I18n.tr("Sunshine Surround 7.1");
        case "sink-sunshine-surround714":
            return I18n.tr("Sunshine Surround 7.1.4");
        default:
            return displayName(node);
        }
    }

    function isVirtualOutput(node) {
        const properties = node?.properties ?? {};
        return properties["node.virtual"] === "true"
            || properties["factory.name"] === "support.null-audio-sink";
    }

    function outputStatus(node) {
        const status = [node === sink ? I18n.tr("Default output") : I18n.tr("Set as default")];
        if (node.audio)
            status.push(node.audio.muted ? I18n.tr("Muted") : Math.round(node.audio.volume * 100) + "%");
        if (isVirtualOutput(node))
            status.push(I18n.tr("Virtual"));
        return status.join(" · ");
    }

'''

PREFER_HARDWARE = (
    "return Number(AudioService.isVirtualOutput(a)) - Number(AudioService.isVirtualOutput(b));"
)


def replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"DMS audio patch expected one instance of {old!r}")
    return source.replace(old, new, 1)


def patch_legacy(detail, slider, grid):
    detail = replace(
        detail, "import qs.Services\n", "import qs.Services\nimport qs.Modules.ControlCenter.Widgets\n"
    )
    detail = re.sub(
        r"    property bool hasVolumeSliderInCC: \{.*?\n    \}\n\n"
        r"    implicitHeight: [^\n]*",
        "    implicitHeight: headerRow.height + audioContent.height + Theme.spacingM",
        detail, count=1, flags=re.S,
    )
    top_slider = detail.index("    Row {\n        id: volumeSlider\n")
    output_list = detail.index("    DankFlickable {\n        id: audioContent\n", top_slider)
    detail = detail[:top_slider] + detail[output_list:]
    detail = replace(detail, "I18n.tr(\"Audio Devices\")", "I18n.tr(\"Audio Outputs\")")
    detail = replace(
        detail, "anchors.top: volumeSlider.visible ? volumeSlider.bottom : headerRow.bottom",
        "anchors.top: headerRow.bottom",
    )
    detail = replace(
        detail, "anchors.topMargin: volumeSlider.visible ? Theme.spacingS : Theme.spacingM",
        "anchors.topMargin: Theme.spacingM",
    )

    start = detail.index("                    id: outputDelegate")
    end = detail.index("            Row {\n                id: playbackHeaderRow", start)
    device = detail[start:end]
    device = replace(device, "                    height: 50", "                    height: 86")
    device = replace(
        device, "                    Row {\n                        anchors.left: parent.left"
        "\n                        anchors.verticalCenter: parent.verticalCenter",
        "                    Row {\n                        anchors.left: parent.left"
        "\n                        anchors.top: parent.top\n                        height: 48",
    )
    device = replace(
        device, "                        anchors.verticalCenter: parent.verticalCenter\n"
        "                        width: pinOutputRow.width",
        "                        anchors.top: parent.top\n                        anchors.topMargin: 10\n"
        "                        width: pinOutputRow.width",
    )
    device = replace(
        device, 'text: modelData === AudioService.sink ? I18n.tr("Active") : I18n.tr("Available")',
        "text: AudioService.outputStatus(modelData)",
    )
    device = replace(
        device, "text: AudioService.displayName(modelData)", "text: AudioService.outputDisplayName(modelData)"
    )
    device = replace(
        device, "                        id: deviceMouseArea\n                        anchors.fill: parent",
        """                        id: deviceMouseArea
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 48
                        enabled: modelData !== AudioService.sink""",
    )
    device = replace(
        device, "                    MouseArea {\n                        id: deviceMouseArea",
        """                    // Fleet per-device audio controls.
                    AudioSliderRow {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.leftMargin: Theme.spacingS
                        anchors.rightMargin: Theme.spacingM
                        anchors.bottomMargin: Theme.spacingXS
                        height: 32
                        defaultSink: outputDelegate.modelData
                        playFeedback: false
                        wheelEnabled: false
                    }

                    MouseArea {
                        id: deviceMouseArea""",
    )
    detail = detail[:start] + device + detail[end:]
    detail = replace(
        detail, "                            return 0;\n                        });",
        f"                            {PREFER_HARDWARE}\n                        }});",
    )
    slider = replace(
        slider, "    property var defaultSink: AudioService.sink",
        """    property var defaultSink: AudioService.sink
    property bool playFeedback: true
    property alias wheelEnabled: volumeSlider.wheelEnabled
    readonly property int maxVolume: AudioService.getMaxVolumePercent(defaultSink)""",
    )
    slider = replace(slider, "maximum: AudioService.sinkMaxVolume", "maximum: root.maxVolume")
    slider = replace(
        slider, "Math.min(AudioService.sinkMaxVolume,", "Math.min(root.maxVolume,"
    )
    slider = replace(
        slider, "                AudioService.playVolumeChangeSoundIfEnabled();",
        "                if (root.playFeedback)\n                    AudioService.playVolumeChangeSoundIfEnabled();",
    )
    slider = replace(
        slider, "        id: volumeSlider",
        "        id: volumeSlider\n        Accessible.name: AudioService.outputDisplayName(root.defaultSink)",
    )
    grid = replace(
        grid, 'return AudioService.sink?.description || I18n.tr("No output device", "audio status");',
        'return AudioService.outputDisplayName(AudioService.sink) || I18n.tr("No output device", "audio status");',
    )
    start = grid.index("            secondaryText: {")
    output = grid.index('case "audioOutput":', start)
    input_ = grid.index('case "audioInput":', output)
    grid = grid[:output] + replace(
        grid[output:input_], 'return Math.round(volume * 100) + "%";',
        'return I18n.tr("Default output") + " · " + Math.round(volume * 100) + "%";',
    ) + grid[input_:]
    return {DETAIL: detail, SLIDER: slider, GRID: grid}


def patch_dux(detail, tile):
    detail = replace(
        detail,
        '''            CcGroup {
                AudioSliderRow {
                    node: AudioService.sink
                    maxVolume: AudioService.sinkMaxVolume
                    playFeedback: true
                }
            }

            CcSectionLabel {
                text: I18n.tr("Audio Devices")
            }

''',
        "",
    )
    detail = replace(detail, 'I18n.tr("Audio Output")', 'I18n.tr("Audio Outputs")')
    detail = replace(
        detail, "                                return 0;\n                            });",
        f"                                {PREFER_HARDWARE}\n                            }});",
    )
    detail = replace(
        detail, "title: AudioService.displayName(modelData)\n",
        "title: AudioService.outputDisplayName(modelData)\n",
    )
    detail = replace(
        detail, 'subtitle: active ? I18n.tr("Active") : I18n.tr("Available")',
        "subtitle: AudioService.outputStatus(modelData)",
    )
    detail = replace(detail, "                        clickable: true", "                        clickable: !active")
    detail = replace(
        detail, "                        DActionButton {",
        """                        // Fleet per-device audio controls.
                        body: AudioSliderRow {
                            node: deviceRow.modelData
                            maxVolume: AudioService.getMaxVolumePercent(node)
                            sliderLabel: deviceRow.title
                        }

                        DActionButton {""",
    )
    tile = replace(
        tile, "title: node?.description ||",
        "title: (isInput ? node?.description : AudioService.outputDisplayName(node)) ||",
    )
    tile = replace(
        tile, 'return Math.round(volume * 100) + "%";',
        'return (isInput ? "" : I18n.tr("Default output") + " · ") + Math.round(volume * 100) + "%";',
    )
    return {DETAIL: detail, TILE: tile}


def patch(shell):
    detail = (shell / DETAIL).read_text()
    if MARKER in detail:
        return
    service = (shell / SERVICE).read_text()
    changes = (
        patch_dux(detail, (shell / TILE).read_text())
        if "CcListRow {" in detail
        else patch_legacy(detail, (shell / SLIDER).read_text(), (shell / GRID).read_text())
    )
    changes[SERVICE] = replace(service, "    function displayName(node) {", OUTPUT_NAME + "    function displayName(node) {")
    for path, contents in changes.items():
        (shell / path).write_text(contents)


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
