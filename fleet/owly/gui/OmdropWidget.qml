import QtQuick
import qs.Common
import qs.Widgets
import qs.Modules.Plugins
PluginComponent {
    id: root
    ccWidgetIcon: "wifi_tethering"
    ccWidgetPrimaryText: "Omdrop AirDrop"
    ccWidgetSecondaryText: !statusPanel.statusChecked ? "Checking…" : statusPanel.blocker ? "Wi-Fi needs attention" : statusPanel.receiving ? "Receiving" : "Not discoverable"
    ccWidgetIsActive: statusPanel.receiving
    ccWidgetIsToggle: true
    ccDetailHeight: 460
    onCcWidgetToggled: {
        if (!statusPanel.busy && statusPanel.statusChecked && (statusPanel.receiving || !statusPanel.blocker))
            statusPanel.run(statusPanel.receiving ? ["off"] : ["on", "10m"]);
    }
    onCcWidgetExpanded: statusPanel.refresh()
    OmdropPanel { id: statusPanel; visible: false; width: 440; height: 460 }
    Timer { interval: 4000; running: true; repeat: true; onTriggered: statusPanel.refresh() }
    ccDetailContent: Component {
        OmdropPanel {
            compact: true
            palette.window: Theme.surface
            palette.base: Theme.surfaceContainer
            palette.windowText: Theme.surfaceText
            palette.text: Theme.surfaceText
            palette.buttonText: Theme.surfaceText
            palette.button: Theme.surfaceContainer
            palette.highlight: Theme.primary
        }
    }
    horizontalBarPill: Component { DankIcon { name: "wifi_tethering"; anchors.centerIn: parent } }
    verticalBarPill: Component { DankIcon { name: "wifi_tethering"; anchors.centerIn: parent } }
    popoutWidth: 520
    popoutHeight: 740
    popoutContent: Component {
        PopoutComponent {
            OmdropPanel {
                width: parent.width; height: 700
                palette.window: Theme.surface
                palette.windowText: Theme.surfaceText
                palette.text: Theme.surfaceText
                palette.buttonText: Theme.surfaceText
                palette.button: Theme.surfaceContainer
            }
        }
    }
}
