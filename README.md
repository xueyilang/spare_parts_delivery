# Trengo 与飞书多维表格中间层服务

这是一个最小可用的 Python HTTP 服务，用于让 Trengo 通过 `POST /lookup-cas` 查询飞书多维表格中的 CAS 记录，并返回 Trengo 可直接使用的 JSON 变量数组。

## 目标

- Trengo 发送 `cas` 到服务
- 服务负责获取飞书 `tenant_access_token`
- 服务查询飞书多维表格中的记录
- 服务返回 Trengo 友好的 JSON 数组
- 环境变量驱动配置，不将密钥写入代码

## 项目结构

- `app.py` - 主 Flask 服务入口
- `feishu_client.py` - 飞书 token 获取与多维表格查询封装
- `requirements.txt` - Python 依赖
- `.python-version` - Python 版本说明
- `.env.example` - 环境变量示例
- `README.md` - 项目说明文档

## 主要接口

### 健康检查

- `GET /`
- 返回 `200` 和 JSON `{"status":"ok"}`

### 核心查询

- `POST /lookup-cas`
- 请求头必须包含：`Authorization: Bearer <shared_secret>`
- 请求体必须是 JSON，包含字段：`cas`
- 如果找到记录，返回 `200` 与字段映射后的数组
- 如果未找到记录，返回 `200` 与 `cas_found=no`
- 如果请求无效或鉴权失败，返回 `400`/`401`

## 环境变量说明

请在 Render 或本地环境中设置以下变量：

- `FEISHU_APP_ID` - 飞书自建应用 `app_id`
- `FEISHU_APP_SECRET` - 飞书自建应用 `app_secret`
- `FEISHU_APP_TOKEN` - 飞书多维表格 `app_token`
- `FEISHU_TABLE_ID` - 飞书多维表格 `table_id`
- `TRANGO_SHARED_SECRET` - Trengo 与本服务共享的 Bearer 密钥
- `PORT` - 可选，Flask 本地启动端口，默认 `5000`

> `PYTHON_VERSION` 可选，仅用于备注，不会被代码读取。

## 字段映射配置

项目内置示例映射：

- `status` -> `Status`
- `customer` -> `Customer`
- `country` -> `Country`

如果飞书多维表格中的字段名不同，请在 `app.py` 中的 `FIELD_MAPPING` 字典里修改。

如果字段在飞书记录中不存在，服务会返回空字符串而不会报错。

## 本地运行

1. 克隆仓库到本地
2. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate    # Windows
```

3. 安装依赖

```bash
pip install -r requirements.txt
```

4. 复制环境变量文件

```bash
copy .env.example .env
```

5. 编辑 `.env`，填入真实值

6. 启动服务

```bash
python app.py
```

7. 测试接口

```bash
curl -X POST http://127.0.0.1:5000/lookup-cas \
  -H "Authorization: Bearer your-secret" \
  -H "Content-Type: application/json" \
  -d '{"cas":"CAS-123456"}'
```

## Render 部署

请使用 Render Web Service 部署，本项目无需 Docker：

- 连接 Git 仓库
- Environment 选择 `Python`
- Build Command:

```bash
pip install -r requirements.txt
```

- Start Command:

```bash
gunicorn app:app
```

然后在 Render 控制台中配置上述环境变量。

> Render 成功部署后会提供一个公网 URL，可直接供 Trengo 调用。

## Trengo 调用示例

```json
POST /lookup-cas HTTP/1.1
Host: your-service-url
Authorization: Bearer your-secret
Content-Type: application/json

{
  "cas": "CAS-123456"
}
```

## 示例响应

### 找到记录

```json
[
  { "key": "cas_found", "value": "yes" },
  { "key": "cas", "value": "CAS-123456" },
  { "key": "status", "value": "Open" },
  { "key": "customer", "value": "Max Mustermann" },
  { "key": "country", "value": "Germany" }
]
```

### 未找到记录

```json
[
  { "key": "cas_found", "value": "no" },
  { "key": "cas", "value": "CAS-123456" }
]
```

## 错误码说明

- `200` - 查询成功，包含记录或未找到
- `400` - 客户端请求错误，例如缺失 `cas` 或无效 JSON
- `401` - 鉴权失败，例如缺失或错误的 `Authorization` header
- `500` - 服务内部异常，例如飞书 API 调用失败或环境变量缺失

## 日志与健壮性

服务使用 Python 标准 `logging`：

- 记录收到请求
- 记录查询 CAS
- 记录飞书查询成功或未找到
- 记录异常信息

服务不会在日志中打印 `app_secret`、`tenant_access_token` 或 `TRANGO_SHARED_SECRET`。

## 进一步扩展

当前实现已保留以下扩展空间：

- Token 缓存
- 更多字段映射
- 多表查询
- 写回飞书
- 支持更多业务键，而不仅是 CAS
