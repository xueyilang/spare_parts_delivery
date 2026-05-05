# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Trengo 与飞书多维表格之间的中间层 HTTP 服务。Trengo 调用 `POST /lookup-cas` 传入 CAS 编号，服务查询飞书多维表格中的物流记录，返回中文自然语言文本供 Trengo AI 使用。

## 技术栈

Python 3.11, Flask, requests, gunicorn (生产环境), python-dotenv

## 开发和运行

```bash
# 安装依赖
pip install -r requirements.txt

# 本地启动 (默认端口 5000，通过 PORT 环境变量配置)
python app.py

# 生产环境启动 (Render)
gunicorn app:app
```

没有测试套件；通过 curl 手动验证：

```bash
curl -X POST http://127.0.0.1:5000/lookup-cas \
  -H "Authorization: Bearer <secret>" \
  -H "Content-Type: application/json" \
  -d '{"cas":"CAS-123456"}'
```

## 架构

项目只有两个源文件，没有共享代码：

- **`app.py`** — Flask 入口。包含：Bearer token 鉴权中间件 (`authorize_request`)、`FIELD_MAPPING` 字典（Trengo 变量名 → 飞书中文字段名），以及用于组装 Trengo 面向用户消息的 `build_ai_message` / `build_single_record_message` / `build_multiple_records_message` 函数。`/lookup-cas` 路由将鉴权、飞书 API 调用、字段映射和消息构建串联在一起，返回 `{"ai_message": "..."}`。

- **`feishu_client.py`** — 底层飞书 API 客户端。两个职责：通过 `get_tenant_access_token()` 获取租户访问令牌（POST 请求至飞书 open-apis），以及通过 `search_record_by_cas()` 查询多维表格记录（POST 请求至 Bitable search endpoint）。`normalize_field_value()` 处理飞书复杂的字段格式（将 dict/list/bool/数字类型递归展开为纯字符串）。

**数据流：** Trengo → `POST /lookup-cas` → 鉴权 → 飞书 token → 飞书记录搜索 → 字段标准化 → FIELD_MAPPING 映射 → 中文消息组合 → 返回给 Trengo 的 `ai_message`

## 环境变量

必填：`FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_APP_TOKEN`、`FEISHU_TABLE_ID`、`TRANGO_SHARED_SECRET`

可选：`FEISHU_SEARCH_FIELD_NAME`（默认 `"客诉号 Ticket Number"`）、`PORT`（默认 `5000`）、`LOG_LEVEL`（默认 `INFO`）

## 关键行为

- `search_record_by_cas` 返回**所有**匹配记录（`page_size: 1`，但循环遍历 items 数组）。在 `app.py` 中映射每个结果，并构建中文摘要，单条记录或多条记录的格式不同。
- 鉴权使用 Bearer token，与 `TRANGO_SHARED_SECRET` 进行明文比对。
- 字段映射对缺失字段具有容错性（返回空字符串，而非抛出异常）。
- 标准 logging 模块，logger 名称为 `trengo_feishu_service`；密钥（app_secret、token、shared_secret）不打印到日志。
