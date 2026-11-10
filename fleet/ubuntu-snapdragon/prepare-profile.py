#!/usr/bin/env python3
"""Generate the user-specific consumer without templating executable user text."""
import json
import pathlib
import shlex
import sys


def profile(run, user, home, revision):
    device = "generic"
    compatible = pathlib.Path('/proc/device-tree/compatible')
    if compatible.exists() and b'hp,omnibook-ultra-kg0xxx' in compatible.read_bytes().split(b'\0'):
        device = 'hp-omnibook-ultra-14-kg0xxx'
    identity = {
        'home.username': user, 'home.homeDirectory': home,
        'home.stateVersion': '26.05', 'programs.hp-os-snapdragon.device': device,
        'programs.hp-os-snapdragon.resumePanelRetrain': device != 'generic',
    }
    target = pathlib.Path(run) / 'profile'
    target.mkdir()
    (target / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    (target / 'flake.nix').write_text('''{
  inputs.desktop-fleet.url = "github:jonathanwilner/simon-hp-os/REVISION";
  inputs.nixpkgs.follows = "desktop-fleet/nixpkgs";
  inputs.home-manager.follows = "desktop-fleet/home-manager";
  outputs = { desktop-fleet, nixpkgs, home-manager, ... }: {
    homeConfigurations.desktop = home-manager.lib.homeManagerConfiguration {
      pkgs = import nixpkgs {
        system = "aarch64-linux"; config.allowUnfree = true;
        overlays = [ desktop-fleet.overlays.chromeChannels ];
      };
      modules = [ desktop-fleet.homeModules.ubuntuSnapdragon
        (let identity = builtins.fromJSON (builtins.readFile ./identity.json);
         in { lib, ... }: lib.mkMerge (lib.mapAttrsToList
           (name: value: lib.setAttrByPath (lib.splitString "." name) value) identity))
      ];
    };
  };
}
'''.replace('REVISION', revision))


def launcher(run, home):
    home = pathlib.Path(home)
    wrapper = home / '.local/bin/hp-os-snapdragon-update'
    script = str(pathlib.Path(run) / 'source/fleet/ubuntu-snapdragon/bootstrap.sh')
    wrapper.write_text('#!/bin/sh\nexec bash ' + shlex.quote(script) + ' "$@"\n')
    wrapper.chmod(0o755)
    desktop = home / '.local/share/applications/hp-os-snapdragon-update.desktop'
    # Desktop Exec quoting differs from shell quoting.
    executable = str(wrapper).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
    desktop.write_text('[Desktop Entry]\nType=Application\nName=Update HP-OS Desktop\n'
                       'Comment=Install the selected public HP-OS desktop release\n'
                       f'Exec="{executable}"\nTerminal=true\nIcon=system-software-update\nCategories=System;\n')


if __name__ == '__main__':
    if sys.argv[1] == '--launcher':
        launcher(*sys.argv[2:])
    else:
        profile(*sys.argv[1:])
