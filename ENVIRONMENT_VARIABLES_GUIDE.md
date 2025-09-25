# DataInsight Agent 环境变量配置指南

## 📋 概述

DataInsight Agent 支持通过环境变量进行灵活配置。以下是所有可用的环境变量及其说明。

## 🔧 配置分类

### 1. **数据库配置**

#### 核心数据库设置
```bash
# 数据库连接URL
DATABASE_URL=sqlite:///./datainsight.db
# MySQL: mysql+pymysql://user:password@localhost:3306/datainsight?charset=utf8mb4
# PostgreSQL: postgresql://user:password@localhost:5432/datainsight
# ClickHouse: clickhouse://user:password@localhost:9000/datainsight

# 数据仓库方言
WAREHOUSE_DIALECT=sqlite  # sqlite | mysql | postgres | clickhouse
```

#### 数据仓库表配置
```bash
# 主表名
DW_TABLE=dws_user_activity_monthly

# 时间列名
DW_TIME_COLUMN=month

# 分区列名（可选）
DW_PARTITION_COLUMN=

# 用户ID列名
DW_USER_ID_COLUMN=user_id

# 活跃标志列名
ACTIVE_FLAG_COLUMN=active

# 允许的列（逗号分隔）
DW_ALLOWED_COLUMNS=
```

### 2. **默认文件路径配置**

```bash
# 默认数据库文件路径
DEFAULT_DB_PATH=datainsight.db

# 默认日志文件路径
DEFAULT_LOG_PATH=logs/datainsight_manual.log

# 默认SQLite路径（CLI命令）
DEFAULT_SQLITE_PATH=./datainsight.db

# 默认KB图路径
DEFAULT_KB_GRAPH_PATH=kb_graph.sqlite
```

### 3. **项目信息配置**

```bash
# 项目名称（用于CLI帮助和日志）
PROJECT_NAME=DataInsight Agent

# 项目描述
PROJECT_DESCRIPTION=Enterprise-grade natural language data agent

# 项目版本
PROJECT_VERSION=0.5.0
```

### 4. **向量存储配置**

```bash
# 向量索引目录
VECTOR_INDEX_DIR=vector_index

# 向量空间（ip | l2）
VECTOR_SPACE=ip

# 向量维度
VECTOR_DIM=384

# 度量向量索引目录
METRIC_INDEX_DIR=metric_index

# Milvus（默认关闭，建议云端接入）
MILVUS_ENABLED=false
MILVUS_URI=
MILVUS_DB=datainsight
MILVUS_COLLECTION=kb_vectors
```

### 5. **图数据库配置**

```bash
# 图后端（local | neo4j | none）
GRAPH_BACKEND=local

# 本地图路径
LOCAL_GRAPH_PATH=kb_graph.sqlite

# Neo4j配置（如果使用neo4j后端）
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=changeme

# 开关（默认关闭，便于本地无依赖运行）
NEO4J_ENABLED=false
```

### 6. **日志配置**

```bash
# 日志级别
LOG_LEVEL=INFO  # DEBUG | INFO | WARNING | ERROR | CRITICAL

# 日志目录
LOG_DIR=logs
```

### 7. **LLM配置**

```bash
# Qwen (DashScope) API密钥（或使用 OPENAI_API_KEY 兼容）
QWEN_API_KEY=

# LLM Q2Q（问题到查询）配置
LLM_Q2Q_ENABLED=1
LLM_Q2Q_TOP_K=6
# 已移除：Q2Q 度量检索相关配置（度量由注册表解析）

# LLM生成控制
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=512
LLM_REQUEST_TIMEOUT=30

# Qwen OpenAI兼容端点与模型
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen2.5-72b-instruct
```

### 8. **检索配置**

```bash
# RAG top-k
RAG_TOP_K=5

# 检索跳过配置
RETRIEVE_SKIP_NO_TIME=1
RETRIEVE_CACHE_ENABLED=1

# 两阶段检索控制
TWO_STAGE_RETRIEVAL_ENABLED=1
RETRIEVAL_TOP_K_STAGE1=12
RETRIEVAL_WEIGHT_VECTOR=0.7
RETRIEVAL_WEIGHT_GRAPH=0.3
RETRIEVAL_OVERFETCH=3
RETRIEVAL_HNSW_EF=64

# 文本检索（Elasticsearch，默认关闭）
ES_ENABLED=false
ES_HOSTS=
ES_INDEX=kb_docs
```

### 9. **编排器配置**

```bash
# 编排器引擎
ORCHESTRATOR_ENGINE=llamaindex  # llamaindex | langgraph
```

### 10. **时间配置**

```bash
# 默认时间窗口（月）
DEFAULT_TIME_WINDOW_MONTHS=12

# 时间要求
TIME_REQUIRE_EXPLICIT=1
TIME_CONFIRM_DEFAULT=1
```

### 11. **元数据配置**

```bash
# 元数据目录
METADATA_DIR=metadata
```

### 12. **工具脚本配置**

```bash
# 工具的默认数据库路径
DB_PATH=datainsight.db
```

## 🚀 使用示例

### 1. **创建.env文件**

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置
nano .env
```

### 2. **基本配置示例**

```bash
# 数据库配置
DATABASE_URL=sqlite:///./datainsight.db
WAREHOUSE_DIALECT=sqlite

# 项目信息
PROJECT_NAME=My DataInsight Agent
PROJECT_VERSION=1.0.0

# 默认路径
DEFAULT_DB_PATH=my_database.db
DEFAULT_LOG_PATH=logs/my_app.log

# LLM配置
OPENAI_API_KEY=sk-your-api-key-here
LLM_Q2Q_ENABLED=1
```

### 3. **生产环境配置示例**

```bash
# 生产数据库
DATABASE_URL=postgresql://user:password@prod-db:5432/datainsight
WAREHOUSE_DIALECT=postgres

# 生产日志
LOG_LEVEL=WARNING
LOG_DIR=/var/log/datainsight

# 生产路径
DEFAULT_DB_PATH=/data/datainsight.db
DEFAULT_LOG_PATH=/var/log/datainsight/app.log

# 性能优化
RETRIEVE_CACHE_ENABLED=1
RAG_TOP_K=10
```

### 4. **开发环境配置示例**

```bash
# 开发数据库
DATABASE_URL=sqlite:///./dev_database.db
WAREHOUSE_DIALECT=sqlite

# 开发日志
LOG_LEVEL=DEBUG
LOG_DIR=logs

# 开发路径
DEFAULT_DB_PATH=dev_database.db
DEFAULT_LOG_PATH=logs/dev.log

# 调试配置
LLM_Q2Q_ENABLED=1
RETRIEVE_CACHE_ENABLED=0
```

## 📝 配置优先级

配置的优先级从高到低：

1. **环境变量** - 最高优先级
2. **Settings类默认值** - 中等优先级
3. **硬编码默认值** - 最低优先级

## 🔍 配置验证

### 1. **检查配置**

```bash
# 运行健康检查
python -m datainsight_agent.cli check
```

### 2. **测试日志**

```bash
# 测试日志配置
python -m datainsight_agent.cli log-test "Test message"
```

### 3. **测试数据库**

```bash
# 初始化数据库
python -m datainsight_agent.cli db-init

# 测试SQL预览
python -m datainsight_agent.cli sql-preview --question "用户活跃度分析"
```

## ⚠️ 注意事项

### 1. **安全考虑**
- 不要在代码中硬编码敏感信息
- 使用环境变量管理API密钥和密码
- 确保.env文件不被提交到版本控制

### 2. **路径配置**
- 使用绝对路径避免相对路径问题
- 确保目录存在且有写权限
- 在生产环境中使用标准路径

### 3. **数据库配置**
- 确保数据库URL格式正确
- 验证数据库方言设置
- 测试数据库连接

### 4. **性能调优**
- 根据数据量调整RAG_TOP_K
- 启用缓存提高性能
- 调整检索参数优化查询速度

## 📚 相关文档

- [项目架构图](PROJECT_ARCHITECTURE_DIAGRAM.md)
- [硬编码修复总结](HARDCODED_FIXES_FINAL_REPORT.md)
- [缓存控制指南](CACHE_CONTROL_GUIDE.md)
