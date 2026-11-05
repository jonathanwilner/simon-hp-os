#!/usr/bin/env python3
"""Wi-Fi Aware GSP/IPP client. Requires the fleet dedicated-radio NAN service.
Wire references: hostap tests/hwsim/test_nan.py; Espressif wa_sd.c GSP TLVs.
No infrastructure connection, driver, firewall or default-route changes.
"""
import argparse
import contextlib
import fcntl
import http.client
import hashlib
import hmac
import ssl
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import struct
import tempfile
import time
from urllib.parse import quote


class PrintError(Exception):
    pass


def identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,15}', value):
        raise PrintError('Invalid interface name')
    return value


def mac(value):
    if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', value):
        raise PrintError('Invalid peer address')
    return value.lower()


def fields(event):
    return dict(re.findall(r'(\w+)=([^ ]*)', event))


def gsp_encode(service):
    if service not in ('_ipp._tcp', '_ipps._tcp'):
        raise PrintError('Only IPP service profiles are supported')
    raw = service.encode()
    return (b'\x50\x6f\x9a\x02' + bytes([2]) + struct.pack('<H', len(raw)) + raw).hex()


def gsp_decode(hexdata):
    try:
        data = bytes.fromhex(hexdata)
    except ValueError as exc:
        raise PrintError('Invalid GSP hex data') from exc
    if data[:4] != b'\x50\x6f\x9a\x02':
        raise PrintError('Printer does not advertise the supported WFA GSP profile')
    result = {}
    pos = 4
    while pos < len(data):
        if pos + 3 > len(data):
            raise PrintError('Truncated GSP header')
        tag, length = data[pos], int.from_bytes(data[pos + 1:pos + 3], 'little')
        pos += 3
        if pos + length > len(data):
            raise PrintError('Truncated GSP value')
        value = data[pos:pos + length]
        pos += length
        if tag in result:
            raise PrintError('Duplicate GSP attribute')
        result[tag] = value
    return result


def txt_decode(data):
    result = {}
    while data:
        length = data[0]
        if length + 1 > len(data):
            raise PrintError('Truncated DNS-SD TXT record')
        value, data = data[1:length + 1], data[length + 1:]
        key, _, val = value.partition(b'=')
        result[key.decode('ascii', errors='strict')] = val.decode('utf-8', errors='strict')
    return result


class Control:
    def __init__(self, path):
        self.directory = tempfile.TemporaryDirectory(prefix='aware-ctrl-')
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(self.directory.name + '/socket')
        self.sock.connect(str(path))
        self.pending = []

    def request(self, command):
        end = time.monotonic() + 5
        self.sock.send(command.encode())
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise PrintError('NAN control response timed out')
            self.sock.settimeout(remaining)
            reply = self.sock.recv(65535).decode(errors='replace').strip()
            if reply.startswith('<') or reply.startswith('IFNAME='):
                self.pending.append(reply)
                continue
            if reply.startswith('FAIL') or reply.startswith('UNKNOWN'):
                # Never echo commands, which may contain credentials.
                raise PrintError('NAN control operation rejected; check driver and supplicant capabilities')
            return reply

    def event(self, prefix, timeout, predicate=lambda x: True):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.pending:
                event = self.pending.pop(0)
            else:
                self.sock.settimeout(max(.01, end - time.monotonic()))
                try:
                    event = self.sock.recv(65535).decode(errors='replace')
                except socket.timeout:
                    return None
            event = re.sub(r'^<\d+>', '', event).strip()
            if event.startswith(prefix) and predicate(fields(event)):
                return fields(event)
        return None

    def close(self):
        self.sock.close()
        self.directory.cleanup()

    def __enter__(self):
        self.request('ATTACH')
        return self

    def __exit__(self, *args):
        self.close()


@contextlib.contextmanager
def subscription(ctrl, service):
    reply = ctrl.request(f'NAN_SUBSCRIBE service_name={service} sync=1 srv_proto_type=2 active=1 ssi={gsp_encode(service)}')
    if not reply.isdigit() or not 1 <= int(reply) <= 255:
        raise PrintError('Invalid subscription response')
    try:
        yield reply
    finally:
        ctrl.request('NAN_CANCEL_SUBSCRIBE subscribe_id=' + reply)


def discover(ctrl, service, timeout, peer=None):
    with subscription(ctrl, service) as handle:
        end = time.monotonic() + timeout
        found = {}
        while time.monotonic() < end:
            event = ctrl.event('NAN-DISCOVERY-RESULT', end - time.monotonic(), lambda e: e.get('subscribe_id') == handle)
            if event is None:
                break
            address = mac(event['address'])
            try:
                info = gsp_decode(event.get('ssi', ''))
            except PrintError:
                continue
            if info.get(2, service.encode()) != service.encode():
                continue
            event['name'] = info.get(3, address.encode()).decode('utf-8', errors='replace')
            found[address] = event
            if peer == address:
                # Keep subscription live until caller finishes data transfer.
                yield handle, event
                return
        if peer:
            raise PrintError('Selected printer did not advertise a compatible IPP service before timeout')
        yield None, list(found.values())


def endpoint(event, discovery, interface, service):
    info = gsp_decode(event.get('ssi', ''))
    previous = gsp_decode(discovery.get('ssi', ''))
    if 0 not in info or len(info[0]) != 2:
        raise PrintError('Printer supplied no valid GSP transport port')
    port = int.from_bytes(info[0], 'little')
    if not port or (1 in info and info[1] != b'\x06'):
        raise PrintError('Printer endpoint is not a valid TCP service')
    iid = event.get('interface_id', '')
    if iid:
        if not re.fullmatch('[0-9a-fA-F]{16}', iid):
            raise PrintError('Invalid NAN IPv6 interface identifier')
        raw = bytes.fromhex(iid)
    else:
        raw_mac = bytes.fromhex(mac(event['peer_ndi']).replace(':', ''))
        raw = bytes([raw_mac[0] ^ 2]) + raw_mac[1:3] + b'\xff\xfe' + raw_mac[3:]
    address = str(ipaddress.IPv6Address(b'\xfe\x80' + b'\0' * 6 + raw))
    txt = txt_decode(previous.get(4, b''))
    resource = txt.get('rp', 'ipp/print')
    if not resource or any(ord(c) < 32 for c in resource) or '?' in resource or '#' in resource:
        raise PrintError('Invalid IPP resource path')
    path = '/' + resource.lstrip('/')
    scheme = 'ipps' if service == '_ipps._tcp' else 'ipp'
    uri = f'{scheme}://[{address}%25{identifier(interface)}]:{port}{quote(path, safe="/")}'
    return address + '%' + interface, port, quote(path, safe='/'), uri


def ipp_attr(tag, name, value):
    name = name.encode()
    if isinstance(value, int):
        value = struct.pack('>i', value)
    elif isinstance(value, str):
        value = value.encode()
    return bytes([tag]) + struct.pack('>H', len(name)) + name + struct.pack('>H', len(value)) + value


def ipp_decode(data, request_id):
    if len(data) < 9 or int.from_bytes(data[4:8], 'big') != request_id:
        raise PrintError('Invalid IPP response')
    status = int.from_bytes(data[2:4], 'big')
    if status >= 0x100:
        raise PrintError(f'Printer rejected IPP operation: 0x{status:04x}')
    attrs, pos, name = {}, 8, ''
    while pos < len(data):
        tag = data[pos]
        pos += 1
        if tag == 3:
            return attrs
        if tag <= 15:
            name = ''
            continue
        if pos + 2 > len(data):
            break
        size = int.from_bytes(data[pos:pos + 2], 'big'); pos += 2
        if pos + size + 2 > len(data):
            break
        if size:
            name = data[pos:pos + size].decode('utf-8', errors='strict')
        pos += size
        size = int.from_bytes(data[pos:pos + 2], 'big'); pos += 2
        if pos + size > len(data):
            break
        value = data[pos:pos + size]; pos += size
        if tag in (0x21, 0x23) and len(value) == 4:
            value = int.from_bytes(value, 'big', signed=True)
        elif tag == 0x22 and len(value) == 1:
            value = bool(value[0])
        else:
            value = value.decode('utf-8', errors='replace')
        attrs.setdefault(name, []).append(value)
    raise PrintError('Truncated IPP response')


class IPP:
    def __init__(self, destination, secure=False, cert_sha256=None):
        self.host, self.port, self.path, self.uri = destination
        self.secure, self.request_id = secure, 0
        self.cert_sha256 = cert_sha256
        if cert_sha256 and (not secure or not re.fullmatch(r'[0-9a-fA-F]{64}', cert_sha256)):
            raise PrintError('Certificate pin requires IPPS and 64 hexadecimal SHA-256 characters')

    def request(self, operation, attrs=(), document=b''):
        self.request_id += 1
        data = struct.pack('>BBHI', 2, 0, operation, self.request_id) + b'\x01'
        data += ipp_attr(0x47, 'attributes-charset', 'utf-8')
        data += ipp_attr(0x48, 'attributes-natural-language', 'en')
        data += ipp_attr(0x45, 'printer-uri', self.uri)
        for tag, name, value in attrs:
            data += ipp_attr(tag, name, value)
        data += b'\x03' + document
        if self.cert_sha256:
            # Explicit certificate pin replaces CA/hostname trust, before any IPP bytes.
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            connection = http.client.HTTPSConnection(self.host, self.port, timeout=30, context=context)
        else:
            connection = (http.client.HTTPSConnection if self.secure else http.client.HTTPConnection)(self.host, self.port, timeout=30)
        try:
            if self.cert_sha256:
                connection.connect()
                actual = hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
                if not hmac.compare_digest(actual, self.cert_sha256.lower()):
                    raise PrintError('Printer TLS certificate does not match the explicitly trusted SHA-256 pin')
            connection.request('POST', self.path, data, {'Content-Type': 'application/ipp'})
            response = connection.getresponse()
            payload = response.read(1024 * 1024 + 1)
            if response.status == 426:
                raise PrintError('Printer requires TLS; select its IPPS service and configure certificate trust')
            if response.status != 200 or len(payload) > 1024 * 1024:
                raise PrintError('Invalid HTTP response from printer')
            return ipp_decode(payload, self.request_id)
        finally:
            connection.close()

    def print_file(self, filename, timeout):
        path = Path(filename)
        if path.stat().st_size > 64 * 1024 * 1024:
            raise PrintError('Print file exceeds the 64 MiB job limit')
        with path.open('rb') as stream:
            data = stream.read(64 * 1024 * 1024 + 1)
        if len(data) > 64 * 1024 * 1024:
            raise PrintError('Print file exceeds the 64 MiB job limit')
        mime = 'application/pdf' if data.startswith(b'%PDF-') else 'image/jpeg' if data.startswith(b'\xff\xd8\xff') else None
        if mime is None:
            raise PrintError('Select a PDF or JPEG file')
        capabilities = self.request(0x000b)
        if mime not in capabilities.get('document-format-supported', []):
            raise PrintError('Printer does not support this document format')
        # Never retry Print-Job automatically: an interrupted response may still mean it printed.
        result = self.request(2, [(0x49, 'document-format', mime), (0x42, 'job-name', path.name)], data)
        ids = result.get('job-id', [])
        if len(ids) != 1 or not isinstance(ids[0], int) or ids[0] <= 0:
            raise PrintError('Job submission response has no valid job ID; inspect printer before retrying')
        job = ids[0]
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            result = self.request(9, [(0x21, 'job-id', job)])
            state = result.get('job-state', [None])[0]
            if state == 9:
                return {'job_id': job, 'job_state': 'completed'}
            if state in (7, 8):
                raise PrintError(f'Printer job {job} was canceled or aborted')
            time.sleep(1)
        raise PrintError(f'Job {job} completion timed out; inspect printer before retrying')


def ndps(ctrl, peer):
    result = set()
    for line in ctrl.request(f'NAN_PEER_INFO {peer} ndps').splitlines():
        entry = fields(line)
        if entry.get('initiator') == '1':
            result.add((mac(entry['init_ndi']), int(entry['ndp_id'])))
    return result


@contextlib.contextmanager
def radio_lock(path='/run/hp-os-aware-print/session.lock'):
    # Service owns the shared lock; do not create a user-private substitute.
    with open(path, 'r+b') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PrintError('Another Wi-Fi Aware operation is active') from exc
        yield


def run_print(ctrl, args):
    with radio_lock():
        return run_print_locked(ctrl, args)


def run_print_locked(ctrl, args):
    peer = mac(args.peer)
    with contextlib.closing(discover(ctrl, args.service, args.timeout, peer)) as discoveries:
        handle, printer = next(discoveries)
        cmd = f'NAN_NDP_REQUEST handle={handle} ndi={identifier(args.data_interface)} peer_nmi={peer} peer_id={int(printer["publish_id"])}'
        if args.passphrase_file:
            file = Path(args.passphrase_file)
            if file.stat().st_mode & 0o077:
                raise PrintError('Passphrase file must be accessible only by its owner')
            secret = file.read_bytes().rstrip(b'\r\n')
            if not 8 <= len(secret) <= 63:
                raise PrintError('NAN passphrase must contain 8 to 63 bytes')
            cmd += ' csid=1 pwd_hex=' + secret.hex()
        elif not args.allow_open:
            raise PrintError('Supply a passphrase file or explicitly select an open printer connection')
        previous = ndps(ctrl, peer)
        event = None
        ctrl.request(cmd)
        try:
            event = ctrl.event('NAN-NDP-CONNECTED', args.timeout, lambda e: e.get('peer') == peer)
            if event is None:
                raise PrintError('NAN data path timed out; no print job was submitted')
            destination = endpoint(event, printer, args.data_interface, args.service)
            return IPP(destination, args.service == '_ipps._tcp', getattr(args, 'cert_sha256', None)).print_file(args.file, args.job_timeout)
        finally:
            cleanup = {(mac(event['local_ndi']), int(event['ndp_id']))} if event else ndps(ctrl, peer) - previous
            for ndi, ndp_id in cleanup:
                ctrl.request(f'NAN_NDP_TERMINATE peer_nmi={peer} init_ndi={ndi} ndp_id={ndp_id}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['doctor', 'discover', 'print'])
    parser.add_argument('--interface', default='hposnan0')
    parser.add_argument('--data-interface', default='hposndi0')
    parser.add_argument('--control-dir', default='/run/hp-os-aware-print/wpa')
    parser.add_argument('--service', choices=['_ipp._tcp', '_ipps._tcp'], default='_ipp._tcp')
    parser.add_argument('--timeout', type=int, default=10)
    parser.add_argument('--job-timeout', type=int, default=120)
    parser.add_argument('--peer')
    parser.add_argument('--file')
    parser.add_argument('--passphrase-file')
    parser.add_argument('--allow-open', action='store_true')
    parser.add_argument('--cert-sha256', help='Explicitly trusted IPPS leaf certificate SHA-256')
    args = parser.parse_args()
    try:
        if not 1 <= args.timeout <= 60 or not 1 <= args.job_timeout <= 3600:
            raise PrintError('Timeout outside supported range')
        identifier(args.interface); identifier(args.data_interface)
        if args.command == 'print' and (not args.peer or not args.file):
            parser.error('print requires --peer and --file')
        with Control(Path(args.control_dir) / args.interface) as ctrl:
            if args.command == 'doctor':
                result = {'nan_status': ctrl.request('NAN_STATUS'), 'data_interface_present': Path('/sys/class/net', args.data_interface).exists(), 'hardware_print_verified': False}
            elif args.command == 'discover':
                with radio_lock(), contextlib.closing(discover(ctrl, args.service, args.timeout)) as discoveries:
                    result = {'printers': next(discoveries)[1]}
            else:
                result = run_print(ctrl, args)
        print(json.dumps({'ok': True, **result}))
        return 0
    except (PrintError, OSError, ValueError, KeyError, http.client.HTTPException) as exc:
        print(json.dumps({'ok': False, 'error': str(exc), 'hint': 'A dedicated NAN-capable radio and the hp-os-aware-print system service are required. Existing Wi-Fi connections are unchanged.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
