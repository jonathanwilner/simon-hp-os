import QtQuick
import qs.Common
import qs.Modules.Plugins

PluginComponent {
    ccWidgetIcon: HdrService.hdrEnabled ? "hdr_on" : "hdr_off"
    ccWidgetPrimaryText: "HDR"
    ccWidgetSecondaryText: HdrService.busy ? "Applying…" :
        (HdrService.hdrEnabled ? HdrService.whiteLevel + " nits" : "Off")
    ccWidgetIsActive: HdrService.available && HdrService.hdrEnabled
    onCcWidgetToggled: {
        if (HdrService.available && !HdrService.busy)
            HdrService.apply(!HdrService.hdrEnabled, HdrService.whiteLevel);
    }
    ccDetailHeight: 420
    ccDetailContent: Component {
        HdrControls { width: parent.width }
    }
}
