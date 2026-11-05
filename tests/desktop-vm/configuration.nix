{ hp-os, home-manager, owly, ... }:
{ config, lib, pkgs, modulesPath, ... }:
let
  shell = hp-os.packages.x86_64-linux.default;
in {
  imports = [
    (modulesPath + "/virtualisation/qemu-vm.nix")
    hp-os.nixosModules.default
    home-manager.nixosModules.home-manager
  ];
  networking.hostName = "hp-os-test";
  system.stateVersion = "26.05";
  nixpkgs.config.allowUnfree = true;
  programs.hp-os = { enable = true; enableBluetooth = false; };
  hardware.graphics.enable = true;
  services.greetd = {
    enable = true;
    settings.default_session = {
      user = "tester";
      command = "${shell}/bin/hp-os session";
    };
  };
  users.users.tester = { isNormalUser = true; extraGroups = [ "wheel" "video" "render" ]; };
  security.sudo.wheelNeedsPassword = false;
  services.openssh = {
    enable = true;
    settings = {
      PasswordAuthentication = false;
      KbdInteractiveAuthentication = false;
      StrictModes = false;
      AuthorizedKeysFile = "/run/hpos-test-share/id_ed25519.pub";
    };
  };
  environment.systemPackages = [ pkgs.grim pkgs.jq pkgs.foot pkgs.curl ];
  home-manager.useGlobalPkgs = true;
  home-manager.useUserPackages = true;
  home-manager.extraSpecialArgs.owlySource = owly;
  home-manager.users.tester = { lib, ... }: {
    imports = [ hp-os.homeManagerModules.default ../../fleet/owly/home.nix ../../fleet/printing/home.nix ../../fleet/relay/home.nix ];
    options.programs.hp-os-fleet.enable = lib.mkOption { type = lib.types.bool; default = true; };
    config = {
      home.username = "tester";
      home.homeDirectory = "/home/tester";
      home.stateVersion = "26.05";
      programs.hp-os.enable = true;
    };
  };
  virtualisation = {
    memorySize = 6144;
    cores = 4;
    diskSize = 12000;
    graphics = true;
    resolution = { x = 1280; y = 800; };
    forwardPorts = [{ from = "host"; host.address = "127.0.0.1"; host.port = 22291; guest.port = 22; }];
    sharedDirectories.hpos-test-share = {
      source = "$HPOS_VM_STATE";
      target = "/run/hpos-test-share";
      writable = true;
    };
    qemu.options = [ "-device virtio-vga-gl" "-vga none" "-display egl-headless,rendernode=/dev/dri/renderD128" "-vnc 127.0.0.1:91" "-qmp unix:$HPOS_VM_STATE/qmp.sock,server=on,wait=off" ];
  };
}
