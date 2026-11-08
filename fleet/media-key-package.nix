{ writeShellApplication, wireplumber, playerctl, coreutils, brightnessctl }:
writeShellApplication {
  name = "hp-os-media-key";
  runtimeInputs = [ wireplumber playerctl coreutils brightnessctl ];
  text = builtins.readFile ./media-key.sh;
}
