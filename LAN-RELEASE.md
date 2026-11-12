# nuc25 局域网发布

客户端入口：http://192.168.110.25:8765/latest.json

public/ 只存本机安装包与当前清单，不进入 Git。releases/VERSION 保存可同步的清单、校验和与来源信息。发布通过源码 scripts/publish_client_release.py 执行。服务只公开 public/，不公开 .git。尚未发布版本时 latest.json 返回 404。
