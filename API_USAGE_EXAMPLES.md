# DataInsight Agent API 使用示例

## 概述

DataInsight Agent 现在提供了完整的 RESTful API 接口，支持通过 HTTP 请求进行自然语言数据查询。

## 启动 API 服务器

```bash
# 使用默认配置启动
uv run -m datainsight_agent.cli api

# 自定义主机和端口
uv run -m datainsight_agent.cli api --host 0.0.0.0 --port 8080

# 启用热重载（开发模式）
uv run -m datainsight_agent.cli api --reload
```

## API 端点

### 1. 健康检查

**GET** `/health`

检查服务状态和版本信息。

```bash
curl -X GET "http://localhost:8000/health"
```

响应示例：
```json
{
  "status": "healthy",
  "version": "0.5.0",
  "timestamp": "2025-09-19T11:52:57.103009"
}
```

### 2. 简单查询（GET）

**GET** `/query/simple`

通过 URL 参数进行简单查询。

```bash
curl -X GET "http://localhost:8000/query/simple?question=用户活跃度分析&user_id=test_user"
```

### 3. 完整查询（POST）

**POST** `/query`

通过 JSON 请求体进行完整查询，支持更多参数。

#### 请求示例

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "2024年1月到5月的用户活跃度分析",
    "user_id": "test_user",
    "validate_sql": true,
    "execute": true,
    "metric_override": "mau",
    "time_filter_override": "2024-01,2024-05"
  }'
```

#### 请求参数

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `question` | string | ✅ | 用户问题（自然语言） |
| `user_id` | string | ❌ | 用户ID（默认：default_user） |
| `validate_sql` | boolean | ❌ | 是否验证SQL（默认：true） |
| `live` | boolean | ❌ | 是否实时执行（默认：false） |
| `execute` | boolean | ❌ | 是否执行SQL（默认：true） |
| `metric_override` | string | ❌ | 指标覆盖 |
| `time_filter_override` | string | ❌ | 时间过滤覆盖 |

#### 响应示例

```json
{
  "success": true,
  "message": "查询处理成功",
  "data": {
    "plan": "execute_sql",
    "ir": {
      "domain_entities": [],
      "target_metrics": [],
      "filters": [
        {
          "field": "active",
          "operator": "=",
          "value": "1"
        },
        {
          "field": "month",
          "operator": "BETWEEN",
          "value": "2024-01,2024-05",
          "time_type": "range",
          "time_unit": "month"
        }
      ],
      "group_by": ["user_level", "month"],
      "aggregations": [
        {
          "function": "COUNT",
          "field": "DISTINCT user_id",
          "alias": "mau"
        }
      ],
      "joins": [],
      "limit": null,
      "order_by": null,
      "attribution_analysis": null,
      "report_type": null
    },
    "sql": "SELECT COUNT(DISTINCT user_id) AS mau, user_level, month FROM dws_user_activity_monthly WHERE active = '1' AND month BETWEEN '2024-01' AND '2024-05' GROUP BY user_level, month",
    "results": [
      {
        "mau": 1500,
        "user_level": "premium",
        "month": "2024-01"
      },
      {
        "mau": 1200,
        "user_level": "basic",
        "month": "2024-01"
      }
    ],
    "attribution_report": null,
    "timing": {
      "q2q": 2.5,
      "retrieve": 0.1,
      "deconstruct": 0.0,
      "plan": 0.0,
      "build_ir": 0.1,
      "execute_or_respond": 0.2
    }
  },
  "error": null,
  "timing": {
    "q2q": 2.5,
    "retrieve": 0.1,
    "deconstruct": 0.0,
    "plan": 0.0,
    "build_ir": 0.1,
    "execute_or_respond": 0.2
  }
}
```

## 编程语言示例

### Python

```python
import requests
import json

# 简单查询
response = requests.get(
    "http://localhost:8000/query/simple",
    params={
        "question": "用户活跃度分析",
        "user_id": "python_client"
    }
)
print(response.json())

# 完整查询
payload = {
    "question": "2024年第一季度各用户等级的活跃度对比",
    "user_id": "python_client",
    "validate_sql": True,
    "execute": True
}

response = requests.post(
    "http://localhost:8000/query",
    headers={"Content-Type": "application/json"},
    data=json.dumps(payload)
)
result = response.json()
print(f"SQL: {result['data']['sql']}")
print(f"结果: {result['data']['results']}")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

// 简单查询
async function simpleQuery() {
    try {
        const response = await axios.get('http://localhost:8000/query/simple', {
            params: {
                question: '用户活跃度分析',
                user_id: 'js_client'
            }
        });
        console.log(response.data);
    } catch (error) {
        console.error('查询失败:', error.response.data);
    }
}

// 完整查询
async function fullQuery() {
    try {
        const response = await axios.post('http://localhost:8000/query', {
            question: '2024年各月份的用户增长趋势',
            user_id: 'js_client',
            validate_sql: true,
            execute: true
        });
        
        const data = response.data.data;
        console.log('执行计划:', data.plan);
        console.log('生成的SQL:', data.sql);
        console.log('查询结果:', data.results);
        console.log('执行时间:', data.timing);
    } catch (error) {
        console.error('查询失败:', error.response.data);
    }
}

simpleQuery();
fullQuery();
```

### PowerShell

```powershell
# 简单查询
$response = Invoke-RestMethod -Uri "http://localhost:8000/query/simple?question=用户活跃度分析&user_id=powershell_client" -Method GET
Write-Host "查询结果: $($response.data.sql)"

# 完整查询
$body = @{
    question = "2024年各用户等级的活跃度分析"
    user_id = "powershell_client"
    validate_sql = $true
    execute = $true
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:8000/query" -Method POST -Body $body -ContentType "application/json"
Write-Host "SQL: $($response.data.sql)"
Write-Host "结果: $($response.data.results)"
```

## 错误处理

API 会返回详细的错误信息：

```json
{
  "success": false,
  "message": "查询处理失败",
  "error": "具体错误信息",
  "data": null,
  "timing": null
}
```

常见错误类型：
- `InternalServerError`: 服务器内部错误
- `ValidationError`: 请求参数验证失败
- `DatabaseError`: 数据库连接或查询错误
- `PermissionError`: 权限验证失败

## 权限验证

API 集成了权限验证模块，默认通过所有权限检查。可以通过 `user_id` 参数指定用户身份：

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "敏感数据查询",
    "user_id": "admin_user"
  }'
```

## 性能监控

API 响应包含详细的执行时间信息：

```json
{
  "timing": {
    "q2q": 2.5,           // Q2Q重写时间
    "retrieve": 0.1,      // 知识库检索时间
    "deconstruct": 0.0,   // 解构时间
    "plan": 0.0,          // 计划制定时间
    "build_ir": 0.1,     // IR构建时间
    "execute_or_respond": 0.2  // 执行或响应时间
  }
}
```

## 最佳实践

1. **使用适当的超时设置**：复杂查询可能需要较长时间
2. **错误重试机制**：实现指数退避重试
3. **结果缓存**：对于相同查询可以缓存结果
4. **用户身份验证**：在生产环境中使用真实的用户认证
5. **监控和日志**：监控API性能和错误率

## 下一步

- 🔄 **Web界面开发**：提供现代化的用户界面
- 📊 **可视化功能**：支持图表生成和仪表板展示
- 🐳 **容器化部署**：Docker容器化部署
- 🔒 **安全增强**：认证授权、数据加密、审计日志
