{ lib, config, ... }:
let
  inherit (lib) mkOption mkEnableOption types;
  cfg = config.programs.hp-os.touchSupport;
in {
  options.programs.hp-os.touchSupport = {
    enable = mkEnableOption "independent touchscreen gestures and optional HP-OS keyboard";
    profile = mkOption { type = types.enum [ "laptop" "convertible" "tablet" "custom" ]; default = "laptop"; };
    gestures = {
      enable = mkOption { type = types.bool; default = true; };
      backend = mkOption { type = types.enum [ "auto" "stock" "niri-tablet" ]; default = "auto"; };
      keyboardEdge = mkOption { type = types.bool; default = false; };
      controlCenterCommand = mkOption { type = types.listOf types.str; default = [ "hp-os" "ipc" "hpos" "controlCenter" ]; };
      controlsEdge = mkOption { type = types.bool; default = false; };
    };
    keyboard = {
      mode = mkOption {
        type = types.enum [ "off" "manual" "tablet-only" "always" ];
        default = if cfg.profile == "tablet" then "always" else if cfg.profile == "convertible" then "tablet-only" else "off";
        description = "Off forbids all OSK processes. Tablet-only requires confirmed posture; touchscreen presence is insufficient.";
      };
      backend = mkOption { type = types.enum [ "hp-os-qml" "celia-qml" "squeekboard" "wvkbd" "none" ]; default = "hp-os-qml"; apply = value: if value == "celia-qml" then "hp-os-qml" else value; };
      fallback = mkOption { type = types.enum [ "squeekboard" "none" ]; default = "squeekboard"; };
      allowFallback = mkOption { type = types.bool; default = true; };
      autoShowOnTextFocus = mkOption { type = types.bool; default = true; };
      showPanelButton = mkOption { type = types.bool; default = true; };
      theme = mkOption { type = types.enum [ "harmonyos" ]; default = "harmonyos"; };
      colorScheme = mkOption { type = types.enum [ "system" "light" "dark" ]; default = "system"; };
      accentColor = mkOption { type = types.str; default = "#3478f6"; };
      languages = mkOption { type = types.listOf (types.enum [ "en_US" "zh_CN" ]); default = [ "en_US" "zh_CN" ]; };
      height = mkOption { type = types.ints.between 180 600; default = 360; };
      keyScale = mkOption { type = types.numbers.between 0.7 1.5; default = 1.0; };
      reducedMotion = mkOption { type = types.bool; default = false; };
      keyPreview = mkOption { type = types.bool; default = true; };
      prediction.enable = mkOption { type = types.bool; default = true; };
      chineseEngine = mkOption { type = types.enum [ "rime" ]; default = "rime"; };
      floating.active = mkOption { type = types.bool; default = false; };
      floating.enable = mkOption { type = types.bool; default = true; };
      haptics.enable = mkOption { type = types.bool; default = false; };
      sound.enable = mkOption { type = types.bool; default = false; };
    };
    rotation = {
      mode = mkOption { type = types.enum [ "off" "tablet-only" "always" ]; default = "off"; };
      output = mkOption { type = types.str; default = ""; description = "Explicit Niri output to rotate; empty disables rotation until selected."; };
    };
  };
}
