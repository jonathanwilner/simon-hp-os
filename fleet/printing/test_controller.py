import argparse
import http.server
import importlib.util
from pathlib import Path
import socket
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('controller', Path(__file__).with_name('controller.py'))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def gsp(**kwargs):
    data = bytes.fromhex(c.gsp_encode('_ipp._tcp'))
    for k, value in kwargs.items():
        data += bytes([int(k)]) + struct.pack('<H', len(value)) + value
    return data.hex()


class ProtocolTests(unittest.TestCase):
    def test_gsp_wire_format_and_truncation(self):
        self.assertEqual(c.gsp_encode('_ipp._tcp'), '506f9a020209005f6970702e5f746370')
        self.assertEqual(c.gsp_decode(gsp(**{'0': b'\x77\x02'}))[0], b'\x77\x02')
        for bad in ['zz', '506f9a0202', '506f9a0202090061', '006f9a02']:
            with self.assertRaises(c.PrintError): c.gsp_decode(bad)

    def test_endpoint_is_link_local_scoped_and_tcp_only(self):
        e = {'ssi': gsp(**{'0': b'\x77\x02', '1': b'\x06'}), 'interface_id': '1122334455667788'}
        d = {'ssi': gsp(**{'4': b'\x0drp=ipp/print'})}
        # Correct TXT length required; malformed lengths fail closed.
        with self.assertRaises(c.PrintError): c.endpoint(e, d, 'ndi0', '_ipp._tcp')
        d['ssi'] = gsp(**{'4': b'\x0crp=ipp/print'})
        host, port, path, uri = c.endpoint(e, d, 'ndi0', '_ipp._tcp')
        self.assertEqual(host, 'fe80::1122:3344:5566:7788%ndi0')
        self.assertEqual(port, 631)
        self.assertIn('%25ndi0', uri)
        e['ssi'] = gsp(**{'0': b'\x77\x02', '1': b'\x11'})
        with self.assertRaises(c.PrintError): c.endpoint(e, d, 'ndi0', '_ipp._tcp')

    def test_control_datagram_events_do_not_confuse_response(self):
        with tempfile.TemporaryDirectory() as directory:
            server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            server.bind(directory + '/server')
            def worker():
                command, peer = server.recvfrom(1024)
                server.sendto(b'<3>NAN-CLUSTER-JOIN cluster=123', peer)
                server.sendto(b'OK', peer)
            thread = threading.Thread(target=worker); thread.start()
            ctrl = c.Control(directory + '/server')
            try:
                self.assertEqual(ctrl.request('NAN_STATUS'), 'OK')
                self.assertEqual(ctrl.event('NAN-CLUSTER-JOIN', 1)['cluster'], '123')
            finally: ctrl.close(); thread.join(); server.close()

    def test_subscription_cleanup_on_failure(self):
        class Ctrl:
            commands = []
            def request(self, cmd):
                self.commands.append(cmd)
                return '4' if cmd.startswith('NAN_SUBSCRIBE') else 'OK'
        ctrl = Ctrl()
        with self.assertRaises(RuntimeError):
            with c.subscription(ctrl, '_ipp._tcp'): raise RuntimeError('test')
        self.assertEqual(ctrl.commands[-1], 'NAN_CANCEL_SUBSCRIBE subscribe_id=4')

    def test_ipp_rejects_mismatched_id_and_error_status(self):
        for data in [struct.pack('>BBHI', 2, 0, 0, 2) + b'\x03', struct.pack('>BBHI', 2, 0, 0x401, 1) + b'\x03']:
            with self.assertRaises(c.PrintError): c.ipp_decode(data, 1)

    def test_real_http_ipp_submission_and_completion(self):
        operations = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                data = self.rfile.read(int(self.headers['Content-Length']))
                operation = int.from_bytes(data[2:4], 'big')
                operations.append(operation)
                response = data[:2] + b'\x00\x00' + data[4:8] + b'\x02'
                if operation == 11:
                    response += c.ipp_attr(0x49, 'document-format-supported', 'application/pdf')
                elif operation == 2:
                    self.server.testcase.assertIn(b'%PDF-test', data)
                    response += c.ipp_attr(0x21, 'job-id', 7)
                else:
                    response += c.ipp_attr(0x23, 'job-state', 9)
                response += b'\x03'
                self.send_response(200); self.end_headers(); self.wfile.write(response)
        server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        server.testcase = self
        thread = threading.Thread(target=server.serve_forever); thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'test.pdf'; path.write_bytes(b'%PDF-test')
                port = server.server_port
                printer = c.IPP(('127.0.0.1', port, '/ipp/print', f'ipp://127.0.0.1:{port}/ipp/print'))
                self.assertEqual(printer.print_file(path, 5), {'job_id': 7, 'job_state': 'completed'})
                self.assertEqual(operations, [11, 2, 9])
        finally:
            server.shutdown(); thread.join(); server.server_close()

    def test_ndp_cleanup_when_print_rejected(self):
        class Ctrl:
            commands = []
            def request(self, command): self.commands.append(command); return 'OK'
            def event(self, *args): return {'peer': '02:00:00:00:00:01', 'local_ndi': '02:00:00:00:00:02', 'ndp_id': '3', 'interface_id': '1122334455667788', 'ssi': gsp(**{'0': b'\x77\x02'})}
        ctrl = Ctrl()
        args = argparse.Namespace(peer='02:00:00:00:00:01', service='_ipp._tcp', timeout=1, data_interface='ndi0', passphrase_file=None, allow_open=True, file='bad', job_timeout=1)
        printer = {'publish_id': '2', 'ssi': c.gsp_encode('_ipp._tcp')}
        with patch.object(c, 'discover', return_value=(x for x in [('1', printer)])), patch.object(c.IPP, 'print_file', side_effect=c.PrintError('rejected')):
            with self.assertRaises(c.PrintError): c.run_print_locked(ctrl, args)
        self.assertEqual(ctrl.commands[-1], 'NAN_NDP_TERMINATE peer_nmi=02:00:00:00:00:01 init_ndi=02:00:00:00:00:02 ndp_id=3')

    def test_radio_lock_excludes_concurrent_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / 'session.lock'
            lock.touch()
            with c.radio_lock(lock):
                with self.assertRaises(c.PrintError):
                    with c.radio_lock(lock): pass
            with c.radio_lock(lock): pass

    def test_tls_pin_checked_before_any_document_bytes(self):
        from unittest.mock import MagicMock
        connection = MagicMock()
        connection.sock.getpeercert.return_value = b'wrong certificate'
        with patch.object(c.http.client, 'HTTPSConnection', return_value=connection):
            printer = c.IPP(('fe80::1%ndi0', 631, '/ipp/print', 'ipps://printer/ipp/print'), True, '0' * 64)
            with self.assertRaises(c.PrintError): printer.request(2, document=b'%PDF-secret')
        connection.request.assert_not_called()
        connection.close.assert_called_once()

    def test_pending_ndp_cleanup_on_timeout_preserves_existing(self):
        class Ctrl:
            def __init__(self): self.commands = []; self.queries = 0
            def request(self, command):
                self.commands.append(command)
                if command.startswith('NAN_PEER_INFO'):
                    self.queries += 1
                    old = 'ndp_id=1 initiator=1 init_ndi=02:00:00:00:00:02'
                    return old if self.queries == 1 else old + '\nndp_id=2 initiator=1 init_ndi=02:00:00:00:00:02'
                return 'OK'
            def event(self, *args): return None
        ctrl = Ctrl()
        args = argparse.Namespace(peer='02:00:00:00:00:01', service='_ipp._tcp', timeout=1, data_interface='ndi0', passphrase_file=None, allow_open=True)
        printer = {'publish_id': '2'}
        closed = []
        def discoveries(*args):
            try: yield '1', printer
            finally: closed.append(True)
        with patch.object(c, 'discover', discoveries):
            with self.assertRaises(c.PrintError): c.run_print_locked(ctrl, args)
        terms = [x for x in ctrl.commands if x.startswith('NAN_NDP_TERMINATE')]
        self.assertEqual(terms, ['NAN_NDP_TERMINATE peer_nmi=02:00:00:00:00:01 init_ndi=02:00:00:00:00:02 ndp_id=2'])
        self.assertEqual(closed, [True])

if __name__ == '__main__': unittest.main()
