#!@python@
"""Publish HP-OS appearance to desktop applications across session buses."""
import configparser
import os
from pathlib import Path
import subprocess
import sys

from hp_os_theme import atomic_write, set_kde_color_scheme, apply_files_palette


def apply(mode):
    if mode not in ('light', 'dark'):
        raise ValueError('appearance must be light or dark')
    dark = mode == 'dark'
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state')))
    # KDE and COSMIC applications keep native preferences separate from GTK's
    # portal preference. Publish all three from the same HP-OS choice.
    set_kde_color_scheme(config / 'kdeglobals', 'BreezeDark' if dark else 'BreezeLight')
    atomic_write(config / 'cosmic/com.system76.CosmicTheme.Mode/v1/is_dark',
                 'true\n' if dark else 'false\n')
    files_profile = Path(os.environ.get('INIR_CONFIG_DIR', str(config / 'hp-os'))) / 'apps/files/kdeglobals'
    if files_profile.exists():
        assets = Path('@filesAssets@')
        if not assets.is_dir():  # source-tree tests
            assets = Path(__file__).with_name('files')
        apply_files_palette(files_profile, assets, mode)
    # GTK3 applications also need the preference in settings.ini. Keep unrelated
    # settings and custom theme names; switch the shipped Adwaita variants.
    gtk_theme = 'Adwaita-dark' if dark else 'Adwaita'
    for version in ('gtk-3.0', 'gtk-4.0'):
        path = config / version / 'settings.ini'
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        if path.exists():
            parser.read(path)
        if 'Settings' not in parser:
            parser['Settings'] = {}
        settings = parser['Settings']
        settings['gtk-application-prefer-dark-theme'] = '1' if dark else '0'
        if settings.get('gtk-theme-name', 'Adwaita') in ('Adwaita', 'Adwaita-dark'):
            settings['gtk-theme-name'] = 'Adwaita-dark' if dark else 'Adwaita'
        if version == 'gtk-3.0':
            gtk_theme = settings.get('gtk-theme-name', gtk_theme)
        from io import StringIO
        output = StringIO()
        parser.write(output, space_around_delimiters=False)
        atomic_write(path, output.getvalue())
    env = dict(os.environ)
    env['GSETTINGS_SCHEMA_DIR'] = '@schemas@'
    # Nix GLib otherwise falls back to a private keyfile when the host's dconf
    # module is unavailable. Portals and GTK apps read dconf, so use the module
    # built with our GLib rather than relying on the launching session's setup.
    env['GSETTINGS_BACKEND'] = 'dconf'
    env['GIO_EXTRA_MODULES'] = '@dconfModules@'
    buses = {env.get('DBUS_SESSION_BUS_ADDRESS', ''),
             'unix:path=' + env.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}') + '/bus'}
    for bus in sorted(buses - {''}):
        env['DBUS_SESSION_BUS_ADDRESS'] = bus
        for key, value in [('color-scheme', 'prefer-' + mode),
                           ('gtk-theme', gtk_theme)]:
            subprocess.run(['@gsettings@', 'set', 'org.gnome.desktop.interface', key, value],
                           env=env, check=True, timeout=10)
    atomic_write(state / 'hp-os/appearance-owner', str(os.getppid()) + '\n')
    atomic_write(state / 'hp-os/appearance-mode', mode + '\n')


if __name__ == '__main__':
    apply(sys.argv[1] if len(sys.argv) == 2 else '')
