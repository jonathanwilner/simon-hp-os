#!/usr/bin/python3
"""Validate Ubuntu account policy without reading or storing a password.

Use the host Python and PAM library for Ubuntu modules and include syntax.
"""
import ctypes as C
import os
import pwd
import sys

user = os.environ.get("PAM_USER", "")
if not user or pwd.getpwnam(user).pw_uid != os.getuid():
    sys.exit(1)
pam = C.CDLL("libpam.so.0")
Callback = C.CFUNCTYPE(C.c_int, C.c_int, C.c_void_p, C.c_void_p, C.c_void_p)
@Callback
def no_prompt(count, messages, responses, data):
    return 19  # PAM_CONV_ERR: account validation must not request a password.
class Conversation(C.Structure):
    _fields_ = [("callback", Callback), ("data", C.c_void_p)]
conversation = Conversation(no_prompt, None)
handle = C.c_void_p()
pam.pam_start.argtypes = [C.c_char_p, C.c_char_p, C.POINTER(Conversation), C.POINTER(C.c_void_p)]
pam.pam_acct_mgmt.argtypes = [C.c_void_p, C.c_int]
pam.pam_end.argtypes = [C.c_void_p, C.c_int]
result = pam.pam_start(b"hp-os-snapdragon-account", user.encode(), C.byref(conversation), C.byref(handle))
if result == 0:
    result = pam.pam_acct_mgmt(handle, 0)
if handle:
    pam.pam_end(handle, result)
sys.exit(0 if result == 0 else 1)
