# Opsie 项目数据库只读连接

本工具用于梳理真实 MySQL 数据，不是应用后端，也不替代正式的数据访问层。
现有 quant_chain/db_mcp 只支持 PostgreSQL 与 ClickHouse，因此这里新增独立的 MySQL 探查入口，没有修改原工具。

当前项目 `.codex/config.toml` 已配置 `opsie_db`。账号信息仅在本机读取根目录的配置文字文件，不写入代码。配置、证书、虚拟环境和本地审计结果通过 `.git/info/exclude` 排除，不提交。

## 运行

```powershell
uv venv .dbmcp-venv --python 3.13
uv pip install --python .dbmcp-venv/Scripts/python.exe -r tools/dbmcp_mysql/requirements.txt
.dbmcp-venv/Scripts/python.exe tools/dbmcp_mysql/pin_certificate.py
.dbmcp-venv/Scripts/python.exe tools/dbmcp_mysql/smoke.py
codex mcp get opsie_db --json
```

证书初始化只在新机器首次进行；存在证书时脚本拒绝覆盖。远端 MySQL 要求 TLS，但提供自签证书，因此先在不发送账号密码的握手中取得证书，后续连接使用该证书为本地信任锚校验。首次信任没有经过带外身份验证；正式部署应由数据库维护者提供可信 CA/证书，并使用匹配的主机名。

## 工具

- `describe_schema`：查看当前数据库字段。
- `use_sql(sql, max_rows)`：单条 SELECT，最多 500 行，单格文本截断到 1500 字符；结果标记是否还有行。SQL 解析检查与 MySQL 只读事务共同限制写入。它用于可信本地开发，不是对恶意 SQL 的完整隔离环境。
- 命令行 `--schema` 或 `--query-file <路径>` 可在当前聊天尚未加载新 MCP 时直接核查。

Codex 已能识别配置，不表示正在运行的聊天自动获得新工具。新的工具列表需客户端重新加载 MCP 后生效。配置方式参考 [官方 MCP 文档](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)。

所有数据库核查均为只读，没有创建账号、私聊、模拟数据或改变原始时间。
