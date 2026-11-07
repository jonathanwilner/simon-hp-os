{ writeShellApplication, wireplumber, playerctl, coreutils }:
writeShellApplication {
  name = "hp-os-media-key";
  runtimeInputs = [ wireplumber playerctl coreutils ];
  text = builtins.readFile ./media-key.sh;
}
