"""Adapt the pinned plugin to Goran's pinned DMS APIs and expose its windows."""

from pathlib import Path

translations = 0
download_flags = 0
for path in Path('.').glob('*.qml'):
    text = path.read_text()
    translations += text.count('I18n.trFor("wallhavenCarousel", ')
    download_flags += text.count('--connect-timeout 10 ')
    text = text.replace('I18n.trFor("wallhavenCarousel", ', 'I18n.tr(')
    text = text.replace('--connect-timeout 10 ', '')
    path.write_text(text)
assert translations > 0, 'Upstream translation calls changed; review compatibility'
assert download_flags == 2, 'Upstream downloader changed; review compatibility'

settings = Path('Settings.qml')
text = settings.read_text()
marker = '    StringSetting {\n'
assert text.count(marker) == 1
text = text.replace(marker, '''    Row {
        spacing: Theme.spacingS
        DankButton {
            text: "Search Wallhaven"
            iconName: "search"
            onClicked: Proc.runCommand("wallhavenCarousel.openSearch", ["dms", "ipc", "call", "wallhavenCarousel", "discover"])
        }
        DankButton {
            text: "Browse local wallpapers"
            iconName: "folder"
            onClicked: Proc.runCommand("wallhavenCarousel.openLibrary", ["dms", "ipc", "call", "wallhavenCarousel", "open"])
        }
    }

''' + marker)
text = text.replace('Empty: DMS\'s cycling folder, or the folder of the current wallpaper.',
                    'Directory for saved wallpapers. Search terms go in Search Wallhaven above.')
settings.write_text(text)
