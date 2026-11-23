"""Add independent output controls to the DMS and Dux control centers."""

import re
import sys
from pathlib import Path

CONTROL_CENTER = Path("Modules/ControlCenter")
DETAIL = CONTROL_CENTER / "Details/AudioOutputDetail.qml"
SLIDER = CONTROL_CENTER / "Widgets/AudioSliderRow.qml"
TILE = CONTROL_CENTER / "Widgets/AudioDeviceTile.qml"
GRID = CONTROL_CENTER / "Components/DragDropGrid.qml"
POPOUT = CONTROL_CENTER / "ControlCenterPopout.qml"
SERVICE = Path("Services/AudioService.qml")
BAR = Path("Modules/DankBar/Widgets/ControlCenterButton.qml")
VOLUME_OSD = Path("Modules/OSD/VolumeOSD.qml")
MARKER = "// Fleet per-device audio controls."
FOCUSED_MARKER = "readonly property bool audioOutputsOpen:"
MAIN_VOLUME_MARKER = "readonly property PwNode mainVolumeSink:"

MAIN_VOLUME = '''
    readonly property string preferredMainOutput: (primaryOutputFile.text() || "").trim()
    readonly property bool mainVolumeUnavailable: !!preferredMainOutput && !mainVolumeSink
    readonly property PwNode mainVolumeSink: {
        if (!preferredMainOutput && !sink?.name?.startsWith("sink-sunshine-"))
            return sink;
        const speakers = Pipewire.nodes.values.filter(node => {
            if (!isPhysicalOutput(node))
                return false;
            return preferredMainOutput ? node.name === preferredMainOutput
                : node.name?.startsWith("alsa_output.usb-Apple_Inc._Studio_Display_")
                    && node.name.endsWith(".analog-stereo");
        });
        if (preferredMainOutput)
            return speakers.length === 1 ? speakers[0] : null;
        return speakers.length === 1 ? speakers[0] : sink;
    }
    readonly property int mainVolumeMax: getMaxVolumePercent(mainVolumeSink)

    FileView {
        id: primaryOutputFile
        path: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/hp-os-primary-audio-output"
        blockLoading: true
        blockWrites: true
        atomicWrites: true
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
    }

    function isPhysicalOutput(node) {
        return !!node?.audio && node.isSink && !node.isStream
            && !node.name?.startsWith("sink-sunshine-") && !isVirtualOutput(node);
    }

    function selectMainVolumeOutput(node) {
        if (isPhysicalOutput(node))
            primaryOutputFile.setText(node.name + "\\n");
    }

    function followDefaultVolumeOutput() {
        primaryOutputFile.setText("");
    }
'''

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


def patch_focused_outputs(detail, popout):
    detail = replace(
        detail,
        "    implicitHeight: headerRow.height + audioContent.height + Theme.spacingM",
        """    property bool showBackButton: false
    signal backRequested

    implicitHeight: headerRow.height + audioColumn.height + Theme.spacingS + Theme.spacingM * 2""",
    )
    detail = replace(
        detail,
        "        StyledText {\n            id: headerText",
        """        DankActionButton {
            id: backButton
            visible: root.showBackButton
            anchors.verticalCenter: parent.verticalCenter
            iconName: I18n.isRtl ? "arrow_forward" : "arrow_back"
            buttonSize: 28
            iconSize: 18
            iconColor: Theme.surfaceVariantText
            Accessible.name: I18n.tr("Back to Control Center")
            onClicked: root.backRequested()
        }

        StyledText {
            id: headerText""",
    )
    detail = replace(
        detail, "width: parent.width - headerText.width - settingsButton.width",
        "width: parent.width - headerText.width - settingsButton.width - (backButton.visible ? backButton.width : 0)",
    )
    popout = replace(
        popout,
        "            readonly property real targetImplicitHeight: {",
        """            readonly property bool audioOutputsOpen: root.expandedSection === "audioOutput" && !root.editMode
            readonly property real targetImplicitHeight: {
                if (audioOutputsOpen)
                    return (audioOutputsView.item?.implicitHeight ?? 0) + Theme.spacingL * 2;""",
    )
    popout = replace(
        popout, "                id: contentFlickable\n",
        "                id: contentFlickable\n                visible: !controlContent.audioOutputsOpen\n",
    )
    popout = replace(
        popout, "                        expandedSection: root.expandedSection\n",
        "                        expandedSection: controlContent.audioOutputsOpen ? \"\" : root.expandedSection\n",
    )
    popout = replace(
        popout,
        "            BluetoothCodecSelector {\n                id: bluetoothCodecSelector",
        """            Loader {
                id: audioOutputsView
                anchors.fill: parent
                anchors.margins: Theme.spacingL
                active: controlContent.audioOutputsOpen
                sourceComponent: Component {
                    AudioOutputDetail {
                        showBackButton: true
                        onBackRequested: root.collapseAll()
                    }
                }
            }

            BluetoothCodecSelector {
                id: bluetoothCodecSelector""",
    )
    return {DETAIL: detail, POPOUT: popout}


def patch_main_volume(service, slider, grid, bar, osd):
    service = replace(
        service, "    readonly property PwNode sink: Pipewire.defaultAudioSink\n",
        "    readonly property PwNode sink: Pipewire.defaultAudioSink\n" + MAIN_VOLUME,
    )
    service = service.replace("root.sinkMaxVolume", "root.mainVolumeMax")
    service = re.sub(r"\broot\.sink\b(?=\??\.audio)", "root.mainVolumeSink", service)
    start = service.index("        function setmaxvolume(")
    end = service.index("        function getmaxvolumefor(", start)
    service = service[:start] + service[start:end].replace("root.sink", "root.mainVolumeSink") + service[end:]
    service = replace(
        service, '                result += `Output: ${volume}%${muteStatus} (max: ${maxVol}%)\\n`;',
        '''                result += `Output: ${volume}%${muteStatus} (max: ${maxVol}%)\\n`;
                if (root.mainVolumeSink !== root.sink)
                    result += `Local output: ${root.outputDisplayName(root.mainVolumeSink)}\\n`;''',
    )
    service = service.replace("adjustDefaultSinkVolume", "adjustMainVolume")
    service = service.replace(
        '"No audio sink available"', '(root.mainVolumeUnavailable ? "Primary speaker unavailable" : "No audio sink available")',
    ).replace(
        'result += "Output: No sink available\\n";',
        'result += (root.mainVolumeUnavailable ? "Output: Primary speaker unavailable\\n" : "Output: No sink available\\n");',
    )
    service = replace(
        service, '        if (isVirtualOutput(node))\n',
        '''        if (node === mainVolumeSink)
            status.push(I18n.tr("Main volume"));
        if (isVirtualOutput(node))
''',
    )

    def volume_target(qml):
        qml = re.sub(r"\bAudioService\.sink\b", "AudioService.mainVolumeSink", qml)
        return re.sub(r"\bAudioService\.sinkMaxVolume\b", "AudioService.mainVolumeMax", qml)

    slider = volume_target(slider)
    grid = volume_target(grid)
    grid = replace(
        grid, 'return AudioService.outputDisplayName(AudioService.mainVolumeSink) || I18n.tr("No output device", "audio status");',
        '''return AudioService.mainVolumeUnavailable ? I18n.tr("Primary speaker unavailable")
                        : AudioService.outputDisplayName(AudioService.mainVolumeSink) || I18n.tr("No output device", "audio status");''',
    )
    grid = replace(
        grid, 'return I18n.tr("Default output") + " · " + Math.round(volume * 100) + "%";',
        '''const role = AudioService.mainVolumeSink === AudioService.sink ? I18n.tr("Default output") : I18n.tr("Local output");
                        return role + " · " + Math.round(volume * 100) + "%";''',
    )
    osd = replace(volume_target(osd), "function onSinkChanged()", "function onMainVolumeSinkChanged()")
    return {SERVICE: service, SLIDER: slider, GRID: grid, BAR: volume_target(bar), VOLUME_OSD: osd}


def patch_main_output_picker(detail):
    detail = replace(
        detail, "width: parent.width - headerText.width - settingsButton.width",
        "width: parent.width - headerText.width - settingsButton.width - (followDefaultButton.visible ? followDefaultButton.width : 0)",
    )
    detail = replace(
        detail, "        DankActionButton {\n            id: settingsButton",
        '''        DankButton {
            id: followDefaultButton
            visible: !!AudioService.preferredMainOutput
            anchors.verticalCenter: parent.verticalCenter
            text: I18n.tr("Follow system default")
            buttonHeight: 28
            horizontalPadding: Theme.spacingS
            onClicked: AudioService.followDefaultVolumeOutput()
        }

        DankActionButton {
            id: settingsButton''',
    )
    detail = replace(
        detail, "                    Rectangle {\n                        anchors.right: parent.right\n                        anchors.rightMargin: Theme.spacingM\n                        anchors.top: parent.top\n                        anchors.topMargin: 10\n                        width: pinOutputRow.width",
        '''                    DankButton {
                        id: mainOutputButton
                        visible: AudioService.isPhysicalOutput(modelData) && modelData.name !== AudioService.preferredMainOutput
                        anchors.right: pinOutputButton.left
                        anchors.rightMargin: Theme.spacingS
                        anchors.verticalCenter: pinOutputButton.verticalCenter
                        text: I18n.tr("Use for main volume")
                        buttonHeight: 28
                        horizontalPadding: Theme.spacingS
                        onClicked: AudioService.selectMainVolumeOutput(modelData)
                    }

                    Rectangle {
                        id: pinOutputButton
                        anchors.right: parent.right
                        anchors.rightMargin: Theme.spacingM
                        anchors.top: parent.top
                        anchors.topMargin: 10
                        width: pinOutputRow.width''',
    )
    detail = replace(
        detail, "const pinButtonWidth = pinOutputRow.width + Theme.spacingS * 4 + Theme.spacingM;",
        "const pinButtonWidth = pinOutputRow.width + Theme.spacingS * 4 + Theme.spacingM + (mainOutputButton.visible ? mainOutputButton.width + Theme.spacingS : 0);",
    )
    return replace(
        detail, "anchors.rightMargin: pinOutputRow.width + Theme.spacingS * 4",
        "anchors.rightMargin: pinOutputRow.width + Theme.spacingS * 4 + (mainOutputButton.visible ? mainOutputButton.width + Theme.spacingS : 0)",
    )


def patch(shell):
    detail = (shell / DETAIL).read_text()
    popout = (shell / POPOUT).read_text()
    supports_focused_outputs = (
        "id: contentFlickable" in popout and "function _contentTargetHeight()" in popout
    )
    service = (shell / SERVICE).read_text()
    is_dux = "CcListRow {" in detail
    changes = {}
    if MARKER not in detail:
        changes.update(
            patch_dux(detail, (shell / TILE).read_text())
            if is_dux
            else patch_legacy(detail, (shell / SLIDER).read_text(), (shell / GRID).read_text())
        )
        changes[SERVICE] = replace(service, "    function displayName(node) {", OUTPUT_NAME + "    function displayName(node) {")
    if supports_focused_outputs and FOCUSED_MARKER not in popout:
        changes.update(patch_focused_outputs(changes.get(DETAIL, detail), popout))
    if not is_dux and MAIN_VOLUME_MARKER not in service:
        changes[DETAIL] = patch_main_output_picker(changes.get(DETAIL, detail))
        changes.update(patch_main_volume(
            changes.get(SERVICE, service),
            changes[SLIDER] if SLIDER in changes else (shell / SLIDER).read_text(),
            changes[GRID] if GRID in changes else (shell / GRID).read_text(),
            (shell / BAR).read_text(),
            (shell / VOLUME_OSD).read_text(),
        ))
    for path, contents in changes.items():
        (shell / path).write_text(contents)


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
