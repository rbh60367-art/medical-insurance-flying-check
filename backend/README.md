# 后端服务

当前为无第三方依赖的最小 HTTP API，用于把规则库和医保 RAG 草案先串起来测试。

## 启动

```powershell
python backend/app/server.py
```

默认监听：

```text
http://127.0.0.1:8010
```

## 接口

```text
GET  /health
GET  /api/v1/stats
GET  /api/v1/policy/search?query=医保支付
GET  /api/v1/rules/search?query=重复收费
POST /api/v1/query/preview
```

`POST /api/v1/query/preview` 示例：

```json
{
  "question": "查询急诊监护费和急诊诊查费是否存在重复收费"
}
```

当前 API 只做预览，不执行 SQL。专家确认后才进入规则执行器和 SQL 模板。
