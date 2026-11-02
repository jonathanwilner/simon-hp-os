#include "state.hpp"
#include <cassert>
int main() {
  InputState s;
  assert(!s.current.active);
  s.activate();
  assert(!s.current.active);
  assert(s.done());
  assert(s.current.active && s.serial == 1);
  s.pending.surrounding = "private";
  s.pending.purpose = 8;
  s.done();
  assert(s.secure() && s.current.surrounding.empty() &&
         s.pending.surrounding.empty());
  s.deactivate();
  assert(s.current.active);
  s.done();
  assert(!s.current.active);
  s.activate();
  s.done();
  assert(!s.secure() && s.current.active);
  s.pending.surrounding = "normal field";
  s.done();
  s.deactivate();
  s.done();
  assert(s.current.surrounding.empty() && s.pending.surrounding.empty());
  s.activate();
  s.done();
  s.pending.hints = 128;
  s.done();
  assert(s.secure());
  s.serial = UINT32_MAX;
  s.done();
  assert(s.serial == 0);
}
