import QtQuick
import qs.Common
import qs.Widgets

Column {
    id: root
    spacing: Theme.spacingM
    property int pendingWhite: HdrService.whiteLevel
    onPendingWhiteChanged: {
        if (whiteSlider.value !== pendingWhite)
            whiteSlider.value = pendingWhite;
    }

    Connections {
        target: HdrService
        function onWhiteLevelChanged() { root.pendingWhite = HdrService.whiteLevel; }
        function onSettingsApplied(white) { root.pendingWhite = white; }
    }
    StyledText {
        width: parent.width
        text: "Internal display HDR"
        font.pixelSize: Theme.fontSizeLarge
        font.weight: Font.Medium
    }
    DankToggle {
        width: parent.width
        text: "Enable HDR"
        description: "Apply to the internal display without logging out."
        checked: HdrService.hdrEnabled
        enabled: HdrService.available && !HdrService.busy
        onToggled: checked => HdrService.apply(checked, HdrService.whiteLevel)
    }
    StyledText {
        width: parent.width
        text: "Desktop white level: " + root.pendingWhite + " nits"
        color: Theme.surfaceText
    }
    DankSlider {
        id: whiteSlider
        width: parent.width
        minimum: 100
        maximum: 500
        step: 10
        unit: " nits"
        leftIcon: "brightness_high"
        value: root.pendingWhite
        enabled: HdrService.available && HdrService.hdrEnabled && !HdrService.busy
        onSliderValueChanged: newValue => root.pendingWhite = newValue
    }
    Column {
        width: parent.width
        spacing: Theme.spacingS
        DankButton {
            width: parent.width
            text: HdrService.busy ? "Applying…" : "Apply white level"
            enabled: HdrService.available && HdrService.hdrEnabled && !HdrService.busy
            onClicked: HdrService.apply(HdrService.hdrEnabled, root.pendingWhite)
        }
        DankButton {
            width: parent.width
            text: "Restore HDR defaults"
            enabled: !HdrService.busy
            onClicked: HdrService.reset()
        }
    }
    StyledText {
        width: parent.width
        text: "Adjusts desktop and SDR content brightness while HDR is enabled. Use the normal brightness slider for panel brightness. Choices survive login and Home Manager updates."
        wrapMode: Text.WordWrap
        font.pixelSize: Theme.fontSizeSmall
        color: Theme.surfaceVariantText
    }
    StyledText {
        width: parent.width
        visible: HdrService.errorText.length > 0
        text: HdrService.errorText
        wrapMode: Text.WordWrap
        color: Theme.error
    }
}
