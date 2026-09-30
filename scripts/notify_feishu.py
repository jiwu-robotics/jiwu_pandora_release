"""Notify the configured Feishu group about an existing stable GitHub release."""
import base64
import hashlib
import hmac
import json
import os
import re
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
    # Release content stays in plain_text nodes so HTML/@mention syntax is inert.
    def plain(text):
        return {'tag': 'plain_text', 'content': text}

    def paragraph(text):
        return {'tag': 'div', 'text': plain(text)}

    body = (release.get('body') or '').strip()
    highlights = []
    for line in body.splitlines():
        if re.match(r'^#{1,6}\s+', line) and highlights:
            break
        match = re.match(r'^\s*[-*+]\s+(.+)', line)
        if match:
            text = re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', match.group(1))
            text = text.replace('`', '').replace('**', '').strip()
            highlights.append(text[:117] + '…' if len(text) > 120 else text)
        if len(highlights) == 5:
            break
    if not highlights:
        lines = [line.strip() for line in body.splitlines() if line.strip() and not line.startswith('#')]
        highlights = [(' '.join(lines)[:240] or '本次更新详情请查看完整发布说明。')]
    elements = []
    if mode == 'test':
        elements.append({'tag': 'note', 'elements': [plain('卡片样式测试 · 使用已有版本信息，并非新版本发布')]})
    elements.append({'tag': 'div', 'fields': [
        {'is_short': True, 'text': plain('发布类型\n正式版' + (' · 补发' if mode == 'backfill' else ''))},
        {'is_short': True, 'text': plain('安装包\n' + ' / '.join(f"{a['size'] / 1024**2:.1f} MiB" for a in assets))},
    ]})
    elements.extend([{'tag': 'hr'},
                     {'tag': 'div', 'text': {'tag': 'lark_md', 'content': '**本次更新**'}},
                     paragraph('\n\n'.join('• ' + item for item in highlights)),
                     {'tag': 'hr'},
                     {'tag': 'div', 'text': {'tag': 'lark_md', 'content': '**安装与升级**'}},
                     paragraph('升级前停止录制、遥操作和拖拽，安全支撑机械臂并关闭客户端。')])
    if release['tag_name'] == 'v2.3.0':
        elements.append(paragraph('适用系统：Ubuntu 22.04 · amd64\n兼容提醒：新 schema 使用新 task name；UMI IMU 按 30 Hz 归档。'))
        elements.append({'tag': 'note', 'elements': [plain('2.3.0 若提示配置无读取权限，执行：sudo chmod 644 /opt/jiwu-abc/site/configs/*.json')]})
    for asset in assets:
        elements.append({'tag': 'action', 'actions': [
            {'tag': 'button', 'text': plain('下载 ' + asset['name']),
             'type': 'primary', 'url': asset['browser_download_url']},
        ]})
    elements.append({'tag': 'action', 'actions': [
        {'tag': 'button', 'text': plain('完整发布说明与校验文件'), 'type': 'default', 'url': release['html_url']},
    ]})
    elements.append({'tag': 'note', 'elements': [plain('Pandora发版小助手 · 摘要仅展示前 5 项，完整变更及验证结果见发布说明')]})
    return {'msg_type': 'interactive', 'card': {
        'config': {'wide_screen_mode': True},
        'header': {'template': 'orange' if mode == 'test' else 'blue', 'title': plain(title)},
        'elements': elements,
    }}


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
