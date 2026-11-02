#!/usr/bin/env python3
"""Control the N1X's eDP OLED luminance through NVIDIA RM DisplayPort AUX.

Only the connected panel with advertised eDP luminance capability is changed.
The RM ioctl layouts and eDP register meanings come from NVIDIA's public GPU
headers and Linux include/drm/display/drm_dp.h.
"""
import argparse
import ctypes as c
import os
import sys

U32 = c.c_uint32
I32 = c.c_int32
U64 = c.c_uint64
U8 = c.c_uint8

class Alloc(c.Structure):
    _fields_ = [('root', U32), ('parent', U32), ('handle', U32), ('klass', I32),
                ('params', U64), ('size', U32), ('status', I32)]

class Control(c.Structure):
    _fields_ = [('client', U32), ('handle', U32), ('command', I32), ('flags', U32),
                ('params', U64), ('size', U32), ('status', I32)]

class Device(c.Structure):
    _fields_ = [('device_id', U32), ('share', U32), ('target_client', U32),
                ('target_device', U32), ('flags', I32), ('pad', U32),
                ('va_size', U64), ('va_start', U64), ('va_limit', U64),
                ('va_mode', I32), ('pad2', U32)]

class Supported(c.Structure):
    _fields_ = [('subdevice', U32), ('mask', U32), ('ddc_mask', U32)]

class Connected(c.Structure):
    _fields_ = [('subdevice', U32), ('flags', U32), ('mask', U32), ('retry_ms', U32)]

class Aux(c.Structure):
    _fields_ = [('subdevice', U32), ('display', U32), ('address_only', U8),
                ('padding', U8 * 3), ('operation', U32), ('address', U32),
                ('data', U8 * 16), ('size', U32), ('reply', U32), ('retry_ms', U32)]

CLIENT, DEVICE, DISPLAY = 0xBB000001, 0xBB000002, 0xBB000003
LIBC = c.CDLL(None, use_errno=True)
LIBC.ioctl.argtypes = (c.c_int, c.c_ulong, c.c_void_p)
LIBC.ioctl.restype = c.c_int

def ioctl(fd, number, obj):
    request = (3 << 30) | (c.sizeof(obj) << 16) | (ord('F') << 8) | number
    if LIBC.ioctl(fd, request, c.byref(obj)) < 0:
        raise OSError(c.get_errno(), os.strerror(c.get_errno()))
    if hasattr(obj, 'status') and obj.status:
        raise RuntimeError(f'NVIDIA RM returned status 0x{obj.status:08x}')

def allocate(fd, parent, handle, klass, params=None):
    item = Alloc(CLIENT, parent, handle, klass,
                 c.addressof(params) if params is not None else 0,
                 c.sizeof(params) if params is not None else 0, 0)
    ioctl(fd, 0x2B, item)

def command(fd, handle, number, params):
    item = Control(CLIENT, handle, number, 0, c.addressof(params), c.sizeof(params), 0)
    ioctl(fd, 0x2A, item)

def aux(fd, display, address, count=0, payload=None):
    packet = Aux()
    packet.display = display
    packet.operation = 0x08 if payload is not None else 0x09
    packet.address = address
    packet.size = len(payload) if payload is not None else count
    if not 1 <= packet.size <= 16:
        raise ValueError('AUX transfer size must be 1..16')
    if payload is not None:
        packet.data[:len(payload)] = payload
    command(fd, DISPLAY, 0x731341, packet)
    return bytes(packet.data[:count]) if payload is None else None

def run(target):
    with open('/dev/nvidiactl', 'rb+', buffering=0) as ctl, open('/dev/nvidia0', 'rb+', buffering=0) as gpu:
        fd = ctl.fileno()
        reg = c.c_int(fd)
        ioctl(gpu.fileno(), 201, reg)
        allocate(fd, CLIENT, CLIENT, 0x41)
        allocate(fd, CLIENT, DEVICE, 0x80, Device())
        allocate(fd, DEVICE, DISPLAY, 0x73)
        supported = Supported()
        command(fd, DISPLAY, 0x730107, supported)
        connected = Connected(0, 1, supported.mask, 0)
        command(fd, DISPLAY, 0x730108, connected)
        panels = []
        for bit in range(32):
            display = 1 << bit
            if not connected.mask & display:
                continue
            try:
                caps = aux(fd, display, 0x700, 4)
            except (OSError, RuntimeError):
                continue
            if len(caps) == 4 and caps[2] & 0x02 and caps[3] & 0x10:
                panels.append((display, caps))
        if len(panels) != 1:
            raise RuntimeError(f'expected one eDP luminance panel; found {len(panels)}')
        display, caps = panels[0]
        mode = aux(fd, display, 0x721, 1)[0]
        enabled = aux(fd, display, 0x720, 1)[0]
        if target is not None:
            if not 5000 <= target <= 500000:
                raise ValueError('target must be between 5000 and 500000 mcd/m²')
            aux(fd, display, 0x720, payload=bytes([enabled | 0x01]))
            aux(fd, display, 0x721, payload=bytes([(mode & ~0x03) | 0x82]))
            aux(fd, display, 0x734, payload=target.to_bytes(3, 'little'))
        actual = int.from_bytes(aux(fd, display, 0x734, 3), 'little')
        new_mode = aux(fd, display, 0x721, 1)[0]
        new_enabled = aux(fd, display, 0x720, 1)[0]
        if target is not None and (actual != target or not new_mode & 0x80 or not new_enabled & 1):
            raise RuntimeError('panel did not retain the requested luminance state')
        print(f'display=0x{display:x} caps={caps.hex()} mode=0x{new_mode:02x} '
              f'enable=0x{new_enabled:02x} target_mcd={actual}')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('target', nargs='?', type=int, help='target luminance in milli-candela/m²')
    args = parser.parse_args()
    try:
        run(args.target)
    except (OSError, RuntimeError, ValueError) as error:
        print(f'goran-panel: {error}', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
