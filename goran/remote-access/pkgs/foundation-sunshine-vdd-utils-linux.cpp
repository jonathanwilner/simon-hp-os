#include "vdd_utils.h"

namespace display_device::vdd_utils {

  const std::chrono::milliseconds kDefaultDebounceInterval { 2000 };

  bool
  is_mode_advertised(const std::string &, const display_mode_t &) {
    return false;
  }

  bool
  wait_for_mode_publication(const std::string &, const display_mode_t &) {
    return false;
  }

  vdd_status_t
  get_vdd_status() {
    return { .state = "unsupported_platform" };
  }

  bool
  hardware_cursor_export_enabled(std::string) {
    return false;
  }

  bool
  ensure_hardware_cursor_enabled_for_capture(bool *changed) {
    if (changed != nullptr) {
      *changed = false;
    }
    return false;
  }

  set_vdd_result
  set_vdd_session_mode(const parsed_config_t &, const VddSettings &) {
    return set_vdd_result::interface_missing;
  }

  std::string
  generate_client_guid(const std::string &) {
    return {};
  }

  physical_size_t
  get_client_physical_size(const std::string &) {
    return {};
  }

  bool
  create_vdd_monitor(const std::string &, const hdr_brightness_t &, const physical_size_t &) {
    return false;
  }

  bool
  create_vdd_monitor_noninteractive() {
    return false;
  }

  bool
  destroy_vdd_monitor() {
    return false;
  }

  void
  destroy_vdd_monitor_nolog() {}

  void
  disable_enable_vdd() {}

  bool
  toggle_display_power() {
    return false;
  }

  bool
  is_display_on() {
    return false;
  }

  bool
  set_hdr_state(bool) {
    return false;
  }

  bool
  ensure_vdd_extended_mode(const std::string &, const std::vector<std::string> &) {
    return false;
  }

  bool
  apply_vdd_prep(const std::string &, parsed_config_t::vdd_prep_e,
    const boost::optional<device_info_map_t> &) {
    return false;
  }

  VddSettings
  prepare_vdd_settings(const parsed_config_t &) {
    return {};
  }

}  // namespace display_device::vdd_utils
