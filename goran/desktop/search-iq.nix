{ pkgs, ... }:
let
  searchIq = import ../../pkgs/hp-os-search-iq { inherit pkgs; };
in {
  home.packages = [ searchIq ];
  systemd.user.services.hp-os-search-iq = {
    Unit = {
      Description = "Ask IQ local search assistant";
    };
    Service = {
      ExecStart = "${searchIq}/bin/hp-os-search-iq";
      Restart = "on-failure";
      RestartSec = 5;
      MemoryMax = "2G";
      CPUQuota = "200%";
      Nice = 10;
      NoNewPrivileges = true;
      PrivateTmp = true;
      UMask = "0077";
    };
    Install.WantedBy = [ "default.target" ];
  };
}
