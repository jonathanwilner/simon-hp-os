{ squeekboard }:
# Rust 1.99 checks libc runtime symbol declarations. Match close(2)'s C ABI;
# retain the upstream KeyMap representation and all other package inputs.
squeekboard.overrideAttrs (old: {
  postPatch = (old.postPatch or "") + ''
    substituteInPlace src/vkeyboard.rs \
      --replace-fail 'fn close(fd: u32);' 'fn close(fd: std::os::raw::c_int) -> std::os::raw::c_int;' \
      --replace-fail 'close(self.fd as u32);' 'close(self.fd as std::os::raw::c_int);'
  '';
})
