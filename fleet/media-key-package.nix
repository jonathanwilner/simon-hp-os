{ writeShellApplication, wireplumber, playerctl }:
writeShellApplication {
  name = "hp-os-media-key";
  runtimeInputs = [ wireplumber playerctl ];
  text = builtins.readFile ./media-key.sh;
}
