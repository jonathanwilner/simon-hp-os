#!/usr/bin/env python3
"""Apply strictly visual HP CDE styling to the existing DMS lock component.

Usage: dms-hp-cde-lock.py SHELL_DIR BANNER_SOURCE [FRAME_SOURCE]
The optional frame source defaults to CdeFrame.qml beside this script.
"""
from pathlib import Path
import hashlib
import shutil
import sys

BASE_SHA = "8ee9c01d234c542183be3e46dfabdb1f6cf8a06e131450dccd4ee5d3bd52e5c6"
MARKER = "// HP_CDE_LOCK_VISUALS_V3"
BASE_SHAS = {BASE_SHA, "17fdca345f8b423c3fe842434a22db8f815e9ec9585b174b801a500f232646d1"}


def transform(text):
    if MARKER in text:
        return text
    if hashlib.sha256(text.encode()).hexdigest() not in BASE_SHAS:
        raise ValueError("Unsupported DMS LockScreenContent.qml revision; preserve it and review visual patch anchors")

    def once(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError(f"Expected exactly one visual anchor: {old[:100]!r}")
        text = text.replace(old, new, 1)

    once('    id: root\n', '    id: root\n    ' + MARKER + '\n    readonly property bool cdeNvidiaGreen: UserInfoService.hostname === "goran"\n')
    if 'readonly property bool hasCustomWallpaper' in text:
        once('        font.pixelSize: 120\n        font.weight: Font.Light',
             '        font.pixelSize: 52\n        font.weight: Font.Normal')
        once('        color: SettingsData.effectiveWallpaperBackgroundColor', '        color: "#000000"')
        once('        active: {\n            if (root.hasCustomWallpaper)', '        visible: false\n        active: {\n            if (root.hasCustomWallpaper)')
        once('        id: wallpaperBackground\n', '        id: wallpaperBackground\n        visible: false\n')
    else:
        once('        active: {\n            var currentWallpaper', '        visible: false\n        active: {\n            var currentWallpaper')
        once('        visible: source !== ""', '        visible: false')
        once('        color: "black"\n        opacity: 0.4', '        color: "black"\n        opacity: 1.0')
        text = text.replace('font.pixelSize: 120', 'font.pixelSize: 52')
        text = text.replace('font.weight: Font.Light', 'font.weight: Font.Normal')
    once('''        Item {
            id: clockContainer''', '''        CdeFrame {
            id: cdePanel
            nvidiaGreen: root.cdeNvidiaGreen
            bevelWidth: 5
            anchors.centerIn: parent
            width: Math.min(780, parent.width - 40)
            height: Math.max(236, passwordLayout.height + 150)

            CdeFrame {
                id: cdePasswordPanel
                nvidiaGreen: root.cdeNvidiaGreen
                x: 15; y: 15
                width: parent.width - cdeLogoPanel.width - 45
                height: parent.height - 30
                Column {
                    x: 20; y: 20
                    width: parent.width - 40
                    spacing: 10
                    Text {
                        width: parent.width
                        text: "Display locked by user " + (UserInfoService.username || "user") + "."
                        font.family: "DejaVu Sans Mono"
                        font.pixelSize: 14
                        color: "#283e59"
                        wrapMode: Text.Wrap
                    }
                    Text {
                        text: "Enter password to unlock."
                        font.family: "DejaVu Sans Mono"
                        font.pixelSize: 14
                        color: "#283e59"
                    }
                    Text {
                        text: "Password:"
                        font.family: "DejaVu Sans Mono"
                        font.pixelSize: 14
                        color: "#283e59"
                    }
                }
            }
            CdeFrame {
                id: cdeLogoPanel
                nvidiaGreen: root.cdeNvidiaGreen
                anchors.right: parent.right
                anchors.rightMargin: 15
                y: 15
                width: Math.min(224, parent.width * 0.30)
                height: parent.height - 30
                Image {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: Math.max(20, (parent.height - height) / 2 - 18)
                    width: parent.width - 20
                    height: width * 141 / 412
                    source: "hp-cde-banner.png"
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    layer.enabled: root.cdeNvidiaGreen
                    layer.effect: MultiEffect {
                        colorization: 1.0
                        colorizationColor: "#76b900"
                    }
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 28
                    text: UserInfoService.hostname || "this computer"
                    color: "#283e59"
                    font.family: "DejaVu Sans Mono"
                    font.bold: true
                    font.pixelSize: 16
                }
            }
        }

        Item {
            id: clockContainer''')
    once('''            anchors.bottom: parent.verticalCenter
            anchors.bottomMargin: 60
            width: parent.width
            height: clockText.implicitHeight''', '''            anchors.bottom: cdePanel.top
            anchors.bottomMargin: (dateText.visible ? dateText.height : 0) + 24
            width: cdePanel.width
            height: visible ? clockText.implicitHeight : 0''')
    once('''            anchors.top: dateText.visible ? dateText.bottom : clockContainer.bottom
            anchors.topMargin: Theme.spacingM''', '''            anchors.top: cdePanel.bottom
            anchors.topMargin: 24''')
    once('''            id: passwordLayout
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: lockNotificationPanel.visible ? lockNotificationPanel.bottom : (dateText.visible ? dateText.bottom : clockContainer.bottom)
            anchors.topMargin: Theme.spacingL
            spacing: Theme.spacingM
            width: 380''', '''            id: passwordLayout
            x: cdePanel.x + cdePasswordPanel.x + 20
            y: cdePanel.y + cdePasswordPanel.y + 100
            spacing: Theme.spacingM
            width: cdePasswordPanel.width - 40''')

    # Keep all input, PAM, service, and notification model code. Scope palette
    # changes to the central panel; the black-screen status bar stays white.
    begin = text.index('        Item {\n            id: clockContainer')
    end = text.index('        StyledText {\n            anchors.top: parent.top', begin)
    center = text[begin:end]
    center = center.replace('width: 75', 'width: 40')
    center = center.replace('width: clockText.hours.length > 1 ? 75 : 0', 'width: clockText.hours.length > 1 ? 40 : 0')
    center = center.replace('radius: 10\n                                        color:', 'radius: 0\n                                        color:')
    # Clock/date remain white above the dialog; field/notification text uses CDE ink.
    split = center.index('            id: lockNotificationPanel')
    center = center[:split] + center[split:].replace('color: "white"', 'color: "#283e59"')
    center = center.replace('color: Qt.rgba(0, 0, 0, 0.3)', 'color: "#a7b9cd"')
    center = center.replace('border.color: Qt.rgba(1, 1, 1, 0.1)', 'border.color: "#72849a"')
    center = center.replace('radius: Theme.cornerRadius - 4', 'radius: 0')
    center = center.replace('radius: Theme.cornerRadius', 'radius: 0')
    center = center.replace('color: Theme.withAlpha(Theme.surfaceContainer, 0.9)', 'color: "#8193a9"')
    center = center.replace('Theme.surfaceText', '"#283e59"')
    center = center.replace('Theme.primarySelected', '"#283e59"')
    center = center.replace('Theme.primary', '"#283e59"')
    center = center.replace('Theme.outline', '"#344c68"')
    center = center.replace('Math.min(fullContentColumn.implicitHeight + Theme.spacingM * 2, 280)', 'Math.min(fullContentColumn.implicitHeight + Theme.spacingM * 2, Math.max(80, root.height - 590))')
    center = center.replace('Math.min(appNamesColumn.implicitHeight + Theme.spacingM * 2, 200)', 'Math.min(appNamesColumn.implicitHeight + Theme.spacingM * 2, Math.max(80, root.height - 590))')
    center = center.replace('            width: 380\n', '            width: Math.min(420, cdePanel.width - 96)\n')
    # Square action controls with matching field color; retain their existing IDs,
    # signals, enabled/visible bindings, and focus/keyboard behavior.
    center = center.replace('DankActionButton {\n', 'DankActionButton {\n                        radius: 0\n                        iconColor: "#283e59"\n')
    text = text[:begin] + center + text[end:]
    # Host-specific palette only; keep every input and authentication handler.
    for old, green in {"#283e59": "#203000", "#a7b9cd": "#b6cf8a",
                       "#72849a": "#527d00", "#8193a9": "#a4c46d",
                       "#344c68": "#365200"}.items():
        text = text.replace('"' + old + '"', '(root.cdeNvidiaGreen ? "' + green + '" : "' + old + '")')
    return text


def main():
    if len(sys.argv) not in (3, 4):
        raise SystemExit(__doc__)
    shell_dir, banner = map(Path, sys.argv[1:3])
    frame = Path(sys.argv[3]) if len(sys.argv) == 4 else Path(__file__).with_name('CdeFrame.qml')
    target = shell_dir / 'Modules/Lock/LockScreenContent.qml'
    result = transform(target.read_text())
    if not banner.is_file() or not frame.is_file():
        raise SystemExit('Missing HP CDE banner or frame asset')
    shutil.copyfile(banner, target.with_name('hp-cde-banner.png'))
    shutil.copyfile(frame, target.with_name('CdeFrame.qml'))
    if target.read_text() != result:
        target.write_text(result)
    print(f'HP CDE lock visuals applied: {target}')


if __name__ == '__main__':
    main()
