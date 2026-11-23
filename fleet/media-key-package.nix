{ writeShellApplication, wireplumber, playerctl, coreutils, brightnessctl, pulseaudio, jq }:
writeShellApplication {
  name = "hp-os-media-key";
  runtimeInputs = [ wireplumber playerctl coreutils brightnessctl pulseaudio jq ];
  text = builtins.readFile ./media-key.sh;
}
