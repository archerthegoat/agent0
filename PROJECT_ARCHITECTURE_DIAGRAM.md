# DataInsight Agent 项目架构图

## 🏗️ 整体架构图

```mermaid
graph TB
    subgraph "用户层"
        CLI[CLI Interface]
        WEB[Web Interface - 待开发]
        API[API Interface - 待开发]
    end
    
    subgraph "编排层 (Orchestrator)"
        LI[LlamaIndex Pipeline]
        Q2Q[Q2Q Component]
        RET[Retrieve Component]
        DEC[Deconstruct Component]
        PLAN[Plan Component]
        IR[Build IR Component]
        EXEC[Execute Component]
    end
    
    subgraph "服务层 (Services)"
        Q2QS[Q2Q Rewriter]
        RETS[Retrieval Service]
        SQLG[SQL Generator]
        SQLV[SQL Validator]
        SQLE[SQL Executor]
        ATTR[Attribution Analyzer]
        TIME[Time Filter Parser]
        METRIC[Metric Retriever]
    end
    
    subgraph "存储层 (Storage)"
        HNSW[HNSW Vector Store]
        SQLITE[SQLite Graph]
        DB[(Database)]
        META[Metadata Files]
    end
    
    subgraph "外部服务"
        LLM[LLM Service]
        EMBED[Embedding Model]
    end
    
    CLI --> LI
    WEB --> LI
    API --> LI
    
    LI --> Q2Q
    LI --> RET
    LI --> DEC
    LI --> PLAN
    LI --> IR
    LI --> EXEC
    
    Q2Q --> Q2QS
    RET --> RETS
    IR --> SQLG
    EXEC --> SQLV
    EXEC --> SQLE
    EXEC --> ATTR
    
    Q2QS --> LLM
    RETS --> HNSW
    RETS --> SQLITE
    SQLG --> DB
    SQLE --> DB
    
    HNSW --> EMBED
    SQLITE --> META
    
    style CLI fill:#e1f5fe
    style WEB fill:#fff3e0
    style API fill:#fff3e0
    style LI fill:#f3e5f5
    style ATTR fill:#e8f5e8
```

## 🔄 数据流图

```mermaid
sequenceDiagram
    participant User as 用户
    participant CLI as CLI
    participant Pipeline as LlamaIndex Pipeline
    participant Q2Q as Q2Q Component
    participant Retrieve as Retrieve Component
    participant IR as IR Builder
    participant SQL as SQL Generator
    participant DB as Database
    
    User->>CLI: 自然语言问题
    CLI->>Pipeline: 启动管道
    Pipeline->>Q2Q: 问题重写
    Q2Q->>Retrieve: 检索知识库
    Retrieve->>IR: 构建IR
    IR->>SQL: 生成SQL
    SQL->>DB: 执行查询
    DB->>SQL: 返回结果
    SQL->>IR: 处理结果
    IR->>Pipeline: 返回最终结果
    Pipeline->>CLI: 输出结果
    CLI->>User: 显示结果
```

## 🧩 组件关系图

```mermaid
graph LR
    subgraph "核心组件"
        A[Q2Q Component]
        B[Retrieve Component]
        C[Deconstruct Component]
        D[Plan Component]
        E[Build IR Component]
        F[Execute Component]
    end
    
    subgraph "支持服务"
        G[Q2Q Rewriter]
        H[Retrieval Service]
        I[SQL Generator]
        J[Attribution Analyzer]
    end
    
    A --> G
    B --> H
    E --> I
    F --> J
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    
    style A fill:#e3f2fd
    style B fill:#e8f5e8
    style C fill:#fff3e0
    style D fill:#f3e5f5
    style E fill:#e1f5fe
    style F fill:#fce4ec
```

## 📊 技术栈图

```mermaid
graph TB
    subgraph "前端层"
        CLI_T[Typer CLI]
        WEB_T[Web UI - 待开发]
    end
    
    subgraph "编排层"
        LI_T[LlamaIndex]
        PYDANTIC[Pydantic v2]
    end
    
    subgraph "服务层"
        STRUCTLOG[structlog]
        RICH[Rich]
        TENACITY[Tenacity]
    end
    
    subgraph "存储层"
        HNSW_T[hnswlib]
        SQLITE_T[SQLite]
        FASTEMBED[FastEmbed]
    end
    
    subgraph "LLM层"
        OPENAI[OpenAI API]
        DEEPSEEK[DeepSeek]
    end
    
    CLI_T --> LI_T
    WEB_T --> LI_T
    LI_T --> PYDANTIC
    LI_T --> STRUCTLOG
    LI_T --> HNSW_T
    LI_T --> OPENAI
    
    style CLI_T fill:#e1f5fe
    style WEB_T fill:#fff3e0
    style LI_T fill:#f3e5f5
    style HNSW_T fill:#e8f5e8
    style OPENAI fill:#fff3e0
```

## 🚀 扩展方向图

```mermaid
graph TB
    subgraph "当前功能"
        A1[Text-to-IR-to-SQL]
        A2[混合知识库]
        A3[归因分析]
        A4[CLI界面]
    end
    
    subgraph "短期扩展"
        B1[Web界面]
        B2[API接口]
        B3[多数据源]
        B4[可视化]
    end
    
    subgraph "中期扩展"
        C1[预测分析]
        C2[异常检测]
        C3[容器化]
        C4[安全增强]
    end
    
    subgraph "长期扩展"
        D1[微服务化]
        D2[多租户]
        D3[AI增强]
        D4[生态建设]
    end
    
    A1 --> B1
    A2 --> B2
    A3 --> B3
    A4 --> B4
    
    B1 --> C1
    B2 --> C2
    B3 --> C3
    B4 --> C4
    
    C1 --> D1
    C2 --> D2
    C3 --> D3
    C4 --> D4
    
    style A1 fill:#e8f5e8
    style A2 fill:#e8f5e8
    style A3 fill:#e8f5e8
    style A4 fill:#e8f5e8
    style B1 fill:#fff3e0
    style B2 fill:#fff3e0
    style B3 fill:#fff3e0
    style B4 fill:#fff3e0
    style C1 fill:#e1f5fe
    style C2 fill:#e1f5fe
    style C3 fill:#e1f5fe
    style C4 fill:#e1f5fe
    style D1 fill:#f3e5f5
    style D2 fill:#f3e5f5
    style D3 fill:#f3e5f5
    style D4 fill:#f3e5f5
```

## 📈 性能优化图

```mermaid
graph LR
    subgraph "缓存层"
        A[类级缓存]
        B[向量存储缓存]
        C[服务实例缓存]
    end
    
    subgraph "并行层"
        D[Q2Q并行]
        E[Retrieve并行]
        F[线程池]
    end
    
    subgraph "优化层"
        G[智能跳过]
        H[延迟加载]
        I[资源管理]
    end
    
    A --> D
    B --> E
    C --> F
    
    D --> G
    E --> H
    F --> I
    
    style A fill:#e8f5e8
    style B fill:#e8f5e8
    style C fill:#e8f5e8
    style D fill:#fff3e0
    style E fill:#fff3e0
    style F fill:#fff3e0
    style G fill:#e1f5fe
    style H fill:#e1f5fe
    style I fill:#e1f5fe
```

## 🔒 安全架构图

```mermaid
graph TB
    subgraph "安全层"
        A[IR层隔离]
        B[SQL验证]
        C[参数化查询]
        D[输入验证]
    end
    
    subgraph "待增强"
        E[认证授权 - 待开发]
        F[数据加密 - 待开发]
        G[审计日志 - 待开发]
        H[权限管理 - 待开发]
    end
    
    A --> E
    B --> F
    C --> G
    D --> H
    
    style A fill:#e8f5e8
    style B fill:#e8f5e8
    style C fill:#e8f5e8
    style D fill:#e8f5e8
    style E fill:#fff3e0
    style F fill:#fff3e0
    style G fill:#fff3e0
    style H fill:#fff3e0
```

## 📊 数据存储架构图

```mermaid
graph TB
    subgraph "向量存储"
        A[kb_vector_index]
        B[metric_index]
        C[vector_index]
    end
    
    subgraph "图数据库"
        D[kb_graph.sqlite]
        E[datainsight.db]
    end
    
    subgraph "元数据"
        F[dimensions.json]
        G[metrics.json]
        H[questions.json]
        I[intent_mappings.json]
    end
    
    subgraph "待扩展"
        J[分布式向量存储]
        K[分布式图数据库]
        L[缓存层]
        M[消息队列]
    end
    
    A --> J
    B --> K
    C --> L
    D --> M
    
    style A fill:#e8f5e8
    style B fill:#e8f5e8
    style C fill:#e8f5e8
    style D fill:#e8f5e8
    style E fill:#e8f5e8
    style F fill:#e8f5e8
    style G fill:#e8f5e8
    style H fill:#e8f5e8
    style I fill:#e8f5e8
    style J fill:#fff3e0
    style K fill:#fff3e0
    style L fill:#fff3e0
    style M fill:#fff3e0
```

## 🎯 总结

这些架构图展示了DataInsight Agent的：

1. **当前状态**: 完整的核心架构和功能
2. **技术栈**: 现代化的技术选型
3. **扩展方向**: 清晰的扩展路径
4. **性能优化**: 多层次的优化策略
5. **安全设计**: 安全优先的设计理念
6. **存储架构**: 灵活的存储方案

通过这些图表，可以清晰地看到项目的现状和未来的发展方向。
