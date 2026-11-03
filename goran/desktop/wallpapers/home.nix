{ config, lib, ... }: {
  config = lib.mkIf config.programs.goran-hp-os.enable {
    home.file."Pictures/Wallpapers/HP-OS" = {
      source = ./images;
      recursive = true;
    };
  };
}
