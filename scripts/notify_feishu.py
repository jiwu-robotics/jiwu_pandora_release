"""Notify the configured Feishu group about an existing stable GitHub release."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NotificationError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url, *, headers=None, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    request = Request(url, data=data, headers=headers or {})
    try:
        with build_opener(NoRedirect).open(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        raise NotificationError(f'HTTP {exc.code}; check service settings. No automatic retry.') from None
    except (URLError, TimeoutError, OSError, ValueError):
        # Never include the webhook URL, request body, or raw service response.
        raise NotificationError('Network/response error; delivery may be uncertain. Check the group before retrying.') from None


def signature(timestamp, secret):
    key = f'{timestamp}\n{secret}'.encode()
    return base64.b64encode(hmac.new(key, b'', hashlib.sha256).digest()).decode()


def build_message(release, mode):
    if mode not in ('release', 'test', 'backfill'):
        raise NotificationError('Unsupported notification mode')
    if release.get('draft') is not False or release.get('prerelease') is not False:
        raise NotificationError('Only published stable releases can be sent')
    assets = [a for a in release.get('assets', [])
              if a['name'].endswith('.deb') and a.get('state') == 'uploaded' and a.get('size', 0) > 0]
    if not assets:
        raise NotificationError('No completed .deb asset; upload assets before publishing')
    prefix = {'test': '【测试消息】', 'backfill': '【补发】', 'release': ''}[mode]
    title = f"{prefix}Pandora 发版通知 · {release['tag_name']}"
    # Rich-text text nodes deliberately do not interpret Markdown/HTML or @mentions.
    rows = [[{'tag': 'text', 'text': release.get('name') or release['tag_name']}]]
    if mode == 'test':
        rows.append([{'tag': 'text', 'text': '机器人连接测试；下方使用真实版本信息，不代表新版本发布。'}])
    body = (release.get('body') or '更新详情请查看 Release 页面。').strip()
    if len(body) > 3500:
        body = body[:3500] + '\n……完整说明请查看 Release。'
    rows.append([{'tag': 'text', 'text': body}])
    for asset in assets:
        rows.append([{'tag': 'a', 'text': f"下载 {asset['name']}（{asset['size'] / 1024**2:.1f} MiB）",
                      'href': asset['browser_download_url']}])
    rows.append([{'tag': 'a', 'text': '查看 Release 与校验文件', 'href': release['html_url']}])
    rows.append([{'tag': 'text', 'text': '升级前请停止录制、遥操作和拖拽，安全支撑机械臂并关闭客户端。'}])
    if release['tag_name'] == 'v2.3.0':
        rows.append([{'tag': 'text', 'text': '2.3.0 已知安装问题：若提示内置配置无读取权限，执行 sudo chmod 644 /opt/jiwu-abc/site/configs/*.json 后重新启动。'}])
    return {'msg_type': 'post', 'content': {'post': {'zh_cn': {'title': title, 'content': rows}}}}


def send_message(payload, webhook, secret):
    parts = urlsplit(webhook)
    if (parts.scheme != 'https' or parts.netloc != 'open.feishu.cn'
            or not parts.path.startswith('/open-apis/bot/v2/hook/')
            or not parts.path.removeprefix('/open-apis/bot/v2/hook/')
            or parts.query or parts.fragment or not secret):
        raise NotificationError('Missing/invalid FEISHU_WEBHOOK_URL or FEISHU_SIGN_SECRET')
    timestamp = str(int(time.time()))
    signed = dict(payload, timestamp=timestamp, sign=signature(timestamp, secret))
    result = request_json(webhook, headers={'Content-Type': 'application/json'}, payload=signed)
    if not isinstance(result, dict):
        raise NotificationError('Invalid Feishu acknowledgment')
    code = result.get('code', result.get('StatusCode'))
    if type(code) is not int or code != 0:
        safe_code = code if type(code) is int else 'missing'
        raise NotificationError(f'Feishu rejected the message (code={safe_code})')
    print('Feishu accepted the notification (code=0). No group readback is available via this webhook.')


def main():
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    event_name = os.environ['GITHUB_EVENT_NAME']
    if event_name == 'release':
        mode, tag = 'release', event['release']['tag_name']
        if event.get('action') != 'published':
            raise NotificationError('Unsupported release action')
    elif event_name == 'workflow_dispatch':
        mode, tag = event['inputs']['mode'], event['inputs']['tag']
        if mode not in ('test', 'backfill'):
            raise NotificationError('Unsupported manual mode')
    else:
        raise NotificationError('Unsupported workflow event')
    repo = os.environ['GITHUB_REPOSITORY']
    release = request_json(f'https://api.github.com/repos/{repo}/releases/tags/{quote(tag, safe="")}',
                           headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                                    'Accept': 'application/vnd.github+json', 'User-Agent': 'Pandora-release-notifier'})
    payload = build_message(release, mode)
    send_message(payload, os.environ.get('FEISHU_WEBHOOK_URL', ''), os.environ.get('FEISHU_SIGN_SECRET', ''))


if __name__ == '__main__':
    try:
        main()
    except (NotificationError, KeyError, ValueError) as exc:
        print(str(exc) if isinstance(exc, NotificationError) else 'Invalid event/release configuration', file=sys.stderr)
        sys.exit(1)
