{ pkgs, ... }:
let
  searchQwen = import ../../pkgs/hp-os-search-qwen { inherit pkgs; };
in {
  home.packages = [ searchQwen ];
  systemd.user.services.hp-os-search-qwen = {
    Unit = {
      Description = "Small local Qwen model for HP-OS search";
      After = [ "graphical-session.target" ];
      PartOf = [ "graphical-session.target" ];
    };
    Service = {
      ExecStart = "${searchQwen}/bin/hp-os-search-qwen";
      Restart = "on-failure";
      RestartSec = 5;
      MemoryMax = "2G";
      CPUQuota = "200%";
      Nice = 10;
      NoNewPrivileges = true;
      PrivateTmp = true;
      UMask = "0077";
    };
    Install.WantedBy = [ "graphical-session.target" ];
  };
}
