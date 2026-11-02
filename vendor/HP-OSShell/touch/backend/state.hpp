#pragma once
#include <cstdint>
#include <string>
struct InputState {
  struct Context {
    bool active = false;
    uint32_t hints = 0, purpose = 0;
    std::string surrounding;
    uint32_t cursor = 0, anchor = 0;
  } current, pending;
  uint32_t serial = 0;
  bool resetPending = false;
  void activate() {
    pending = {};
    pending.active = true;
    resetPending = true;
  }
  void deactivate() {
    pending.active = false;
    resetPending = true;
  }
  bool secure() const {
    return current.purpose == 8 || current.purpose == 9 ||
           (current.hints & (64 | 128));
  }
  bool done() {
    bool reset = resetPending;
    current = pending;
    ++serial;
    resetPending = false;
    if (!current.active || secure()) {
      current.surrounding.clear();
      pending.surrounding.clear();
    }
    return reset;
  }
};
