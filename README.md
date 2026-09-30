# JIWU-Pandora releases

Public installers for the JIWU-Pandora robot data collection client.

- Ubuntu 22.04 amd64: install the `.deb` asset with `sudo apt install ./jiwu-pandora_VERSION_amd64.deb`. Python 3.12 is included.
- Python 3.12: unpack the offline bundle and run `bash install-python.sh /absolute/path/to/venv`.
- Verify downloads using the release's SHA256SUMS.
- Stop recording/teleoperation/drag, safely support the arms, and close the client before installation.
- Existing clients: set the update repository to `jiwu-robotics/jiwu_pandora_release` in update settings; leave the token empty. Check for updates and download the verified package. Installation requires local administrator authorization.
- The Debian package identifier remains `jiwu-abc` for upgrades from older versions; the product and launch command are JIWU-Pandora / `jiwu-pandora`.

Installers are in GitHub Releases. Source development is maintained separately in the private `jiwu-robotics/jiwu_pandora` repository. Publishing a release makes it available to clients; it does not force installation on running equipment.

## 飞书发版通知

`.github/workflows/release-feishu.yml` 向 **Pandora发版群** 的 **Pandora发版小助手** 发送通知，不 @人。群和机器人实际由 Webhook 所属机器人决定。

在本仓库 Settings → Secrets and variables → Actions 配置：

- `FEISHU_WEBHOOK_URL`：群自定义机器人的 Webhook。
- `FEISHU_SIGN_SECRET`：该机器人启用「签名校验」后生成的密钥。

正式 Release 发布 (`release.published`) 后自动发送；草稿、预发布不发送。请先上传所有附件，再发布草稿。消息使用彩色标题卡片，包含版本、前 5 条更新摘要（每条最多 120 字）、deb 下载按钮及大小、完整 Release 按钮和升级注意事项。正式通知为蓝色，测试为橙色；外部文本使用 plain_text，不解析 @人语法。仅依赖 Python 标准库，不安装第三方包。

手动测试或补发：Actions → **Release to Feishu** → **Run workflow**，选择 `main`，填写已发布正式版 tag（例如 `v2.3.0`）；`mode=test` 发送带「测试消息」前缀的真实版本信息，`mode=backfill` 发送带「补发」前缀的信息。

每次工作流执行只请求发送一次；同一 tag 的执行串行处理，不自动重试。手动重跑或补发可能重复发送。若网络超时，先查看群中是否收到消息，再决定重跑。Actions 成功表示飞书接口返回成功，不代表群成员已读。非零业务错误会使工作流失败，日志不输出 Webhook/签名密钥。

当前本地 `gh` 发布方式可触发 Release 事件。若以后在 Actions 中使用 `GITHUB_TOKEN` 创建 Release，该事件不会再触发其他工作流；需要使用有权限的 GitHub App/PAT 发布，或在发布流程完成后显式调用本工作流的 `workflow_dispatch` 补发入口（需要 `actions: write`）。

停用/回滚：在 Actions 中 Disable workflow，或通过新提交撤销通知配置。已发送的群消息不会因回滚撤回。

本地验证：`python3 -m unittest discover -s tests -v`。测试使用模拟请求，不发送群消息。
