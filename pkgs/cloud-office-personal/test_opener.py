import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location('opener', Path(__file__).with_name('opener.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class OfficeTests(unittest.TestCase):
    def test_rejects_untrusted_cloud_links(self):
        for url in ['http://tenant.sharepoint.com/x', 'https://tenant.sharepoint.com.evil/x', 'https://user:secret@tenant.sharepoint.com/x']:
            self.assertFalse(m.cloud_url(url))
        self.assertTrue(m.cloud_url('https://tenant.sharepoint.com/x.docx'))

    def test_direct_url_needs_no_personal_graph_signin(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp}), patch.object(m, 'token') as token, patch.object(m, 'launch') as launch:
            self.assertEqual(m.main(['https://tenant.sharepoint.com/example.docx']), 0)
            token.assert_not_called()
            self.assertIn('web=1', launch.call_args.args[0])

    def test_configuration_stores_no_password_and_resets_tokens(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp}):
            state = m.state_dir()
            (state / 'tokens.json').write_text('old')
            self.assertEqual(m.main(['--configure', '12345678-1234-1234-1234-123456789abc']), 0)
            self.assertEqual(json.loads((state / 'account.json').read_text()), {'client_id': '12345678-1234-1234-1234-123456789abc', 'tenant': 'common'})
            self.assertFalse((state / 'tokens.json').exists())
            self.assertEqual((state / 'account.json').stat().st_mode & 0o777, 0o600)

    def test_existing_cloud_edits_are_not_uploaded_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'Document.docx'
            path.write_bytes(b'office document')
            with patch.object(m, 'folder', side_effect=['office', 'digest']), patch.object(m, 'graph', side_effect=[{'id': 'root'}, {'webUrl': 'https://tenant.sharepoint.com/Document.docx'}]) as graph:
                result = m.upload('private', path)
                self.assertIn('web=1', result)
                self.assertEqual([call.args[1] for call in graph.call_args_list], ['GET', 'GET'])

    def test_upload_session_is_fail_on_conflict_and_uses_no_bearer_for_payload(self):
        missing = HTTPError('https://graph.microsoft.com', 404, 'missing', {}, None)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'Document.docx'
            path.write_bytes(b'office document')
            result = io.BytesIO(json.dumps({'webUrl': 'https://tenant.sharepoint.com/Document.docx'}).encode())
            with patch.object(m, 'folder', side_effect=['office', 'digest']), patch.object(m, 'graph', side_effect=[{'id': 'root'}, missing, {'uploadUrl': 'https://upload.example.invalid/session'}]) as graph, patch.object(m, 'urlopen', return_value=result) as request:
                m.upload('private', path)
                self.assertEqual(graph.call_args.args[3]['item']['@microsoft.graph.conflictBehavior'], 'fail')
                self.assertNotIn('Authorization', request.call_args.args[0].headers)
                self.assertEqual(request.call_args.args[0].headers['Content-range'], 'bytes 0-14/15')

    def test_paths_cannot_target_other_hosts(self):
        with self.assertRaises(ValueError):
            m.checked_path('file://otherhost/document.docx')
        with self.assertRaises(ValueError):
            m.checked_path('https://untrusted.example/document.docx')

    def test_document_icons_keep_app_type(self):
        self.assertEqual(m.document_app('https://tenant.sharepoint.com/:w:/r/doc'), 'word')
        self.assertEqual(m.document_app('https://tenant.sharepoint.com/Doc.aspx?file=sheet.xlsx'), 'excel')


if __name__ == '__main__':
    unittest.main()
