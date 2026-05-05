# Trengo 与飞书多维表格中间层服务

让 Trengo 通过 `POST /lookup-cas` 查询飞书多维表格中的物流记录，返回英文自然语言文本供 Trengo AI 使用，面向欧洲安装商。

## 项目结构

- `app.py` - Flask 服务入口，鉴权、字段映射、值清洗、消息构建
- `feishu_client.py` - 飞书 API 封装（token 获取、多维表格查询）
- `test_regression.py` - 回归测试（84+ 用例）
- `requirements.txt` - Python 依赖
- `.env.example` - 环境变量示例

## 接口

### `GET /` — 健康检查

返回 `{"status": "ok"}`，状态码 200。

### `POST /lookup-cas` — 核心查询

请求头：
- `Authorization: Bearer <TRANGO_SHARED_SECRET>`
- `Content-Type: application/json`

请求体：`{"cas": "CAS-123456"}`

响应：`{"ai_message": "..."}`

## 消息逻辑

| 场景 | 输出示例 |
|---|---|
| 未找到 | `No logistics record found for CAS CAS-00000000.` |
| 状态 ≠ Shipped（已取消/未处理） | `Status: Shipment cancelled.` |
| 已发货 + 有物流单号 | `Tracking number: 60104324929, Status: Shipped, Forwarder: GLS.` |
| 已发货 + 无物流单号 | `Tracking number: not available, Status: Shipped, Forwarder: NTS-Logistik Partner.` |
| 已发货 + 多物流单号 | `Tracking number: 60105718349, 60105859391, Status: Shipped, Forwarder: GLS.` |

## 字段映射

| Trengo 变量名 | 飞书表格字段名 |
|---|---|
| `tracking_number` | 物流单号(发货) Tracking Number |
| `logistics_status` | 物流状态 Logistics Status |
| `freight_forwarder` | 货代（售后物流发货）Freight Forwarder |

## 字段值清洗

服务自动处理飞书表格中的中英混合值和占位符：

- **状态**：`"已发货 Shipped"` → `"Shipped"`，`"已取消 Shipment cancelled"` → `"Shipment cancelled"`
- **物流单号**：提取纯数字，过滤占位符（`NTS物流`、`Selbstabholung`、`LHZ-DPD`），支持一字段多个单号
- **承运商**：`"安装商或客户自提"` → `"Self pick-up"`

## 环境变量

必填：
- `FEISHU_APP_ID` - 飞书自建应用 app_id
- `FEISHU_APP_SECRET` - 飞书自建应用 app_secret
- `FEISHU_APP_TOKEN` - 飞书多维表格 app_token
- `FEISHU_TABLE_ID` - 飞书多维表格 table_id
- `TRANGO_SHARED_SECRET` - Trengo 与本服务的共享 Bearer 密钥

可选：
- `FEISHU_SEARCH_FIELD_NAME` - CAS 查询字段名，默认 `"客诉号 Ticket Number"`
- `PORT` - 本地端口，默认 `5000`
- `LOG_LEVEL` - 日志级别，默认 `INFO`

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate       # macOS / Linux
.venv\Scripts\activate          # Windows

pip install -r requirements.txt
cp .env.example .env            # 编辑 .env 填入真实值
python app.py
```

测试接口：

```bash
curl -X POST http://127.0.0.1:5000/lookup-cas \
  -H "Authorization: Bearer <secret>" \
  -H "Content-Type: application/json" \
  -d '{"cas":"CAS-145296"}'
```

## 运行测试

```bash
python test_regression.py
```

## Render 部署

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- Region: Frankfurt（面向欧洲）
- 在 Render Dashboard → Environment 中添加上述环境变量

## 错误码

| 状态码 | 说明 |
|---|---|
| 200 | 查询成功 |
| 400 | 请求无效（缺少 cas 字段、无效 JSON） |
| 401 | 鉴权失败（缺少或错误的 Authorization header） |
| 500 | 服务内部异常（飞书 API 失败、环境变量缺失） |
