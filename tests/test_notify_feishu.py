import copy
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('notify', Path(__file__).resolve().parents[1] / 'scripts/notify_feishu.py')
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)


class NotifyTests(unittest.TestCase):
    def setUp(self):
        self.release = dict(tag_name='v2.3.0', name='Pandora 2.3.0', draft=False, prerelease=False,
                            body='<at user_id="all">所有人</at> $(echo unsafe)', html_url='https://github.com/r/releases/tag/v2.3.0',
                            assets=[dict(name='pandora.deb', size=1048576, state='uploaded', browser_download_url='https://github.com/r/pandora.deb')])

    def test_signature(self):
        import base64
        import hashlib
        import hmac
        expected = base64.b64encode(hmac.digest(b'123\nsecret', b'', hashlib.sha256)).decode()
        self.assertEqual(n.signature('123', 'secret'), expected)

    def test_stable_only(self):
        for field in ('draft', 'prerelease'):
            release = copy.deepcopy(self.release)
            release[field] = True
            with self.assertRaises(n.NotificationError):
                n.build_message(release, 'release')

    def test_missing_asset(self):
        self.release['assets'] = []
        with self.assertRaises(n.NotificationError):
            n.build_message(self.release, 'release')

    def test_no_mentions_and_test_label(self):
        post = n.build_message(self.release, 'test')['content']['post']['zh_cn']
        self.assertTrue(post['title'].startswith('【测试消息】'))
        self.assertEqual(post['content'][2][0]['text'], self.release['body'])
        self.assertTrue(all(node['tag'] in ('text', 'a') for row in post['content'] for node in row))

    def test_body_is_bounded(self):
        self.release['body'] = 'a' * 10000
        post = n.build_message(self.release, 'backfill')['content']['post']['zh_cn']
        self.assertLess(len(post['content'][1][0]['text']), 3600)

    @patch.object(n, 'request_json')
    def test_acknowledgment(self, request):
        for ack in ({'code': 0}, {'StatusCode': 0}):
            request.return_value = ack
            n.send_message({}, 'https://open.feishu.cn/open-apis/bot/v2/hook/example', 'secret')
        for ack in ({'code': 19021}, {}, {'code': False}):
            request.return_value = ack
            with self.assertRaises(n.NotificationError):
                n.send_message({}, 'https://open.feishu.cn/open-apis/bot/v2/hook/example', 'secret')

    @patch.object(n, 'request_json')
    def test_invalid_credentials_never_sent(self, request):
        for url, secret in [('', ''), ('https://evil.example/hook', 'secret'),
                            ('https://open.feishu.cn/open-apis/bot/v2/hook/example', '')]:
            with self.assertRaises(n.NotificationError):
                n.send_message({}, url, secret)
        request.assert_not_called()
