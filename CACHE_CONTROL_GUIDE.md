# Retrieve组件缓存控制指南

## 概述

DataInsight Agent的retrieve组件现在支持通过环境变量控制缓存机制，这为调试和性能测试提供了灵活性。

## 环境变量

### `RETRIEVE_CACHE_ENABLED`

- **类型**: 布尔值
- **默认值**: `true`
- **作用**: 控制retrieve组件是否使用缓存机制

## 使用方法

### 启用缓存（默认行为）

```bash
# Windows PowerShell
$env:RETRIEVE_CACHE_ENABLED="true"
uv run -m datainsight_agent.cli run --question "你的问题" --validate

# Linux/macOS
export RETRIEVE_CACHE_ENABLED=true
uv run -m datainsight_agent.cli run --question "你的问题" --validate
```

### 禁用缓存

```bash
# Windows PowerShell
$env:RETRIEVE_CACHE_ENABLED="false"
uv run -m datainsight_agent.cli run --question "你的问题" --validate

# Linux/macOS
export RETRIEVE_CACHE_ENABLED=false
uv run -m datainsight_agent.cli run --question "你的问题" --validate
```

## 缓存机制说明

### 启用缓存时
- 使用类级缓存的`EmbeddingModel`实例
- 使用类级缓存的`LocalHNSWVectorStore`实例
- 避免重复的模型加载和索引构建
- 提高多次查询的响应速度

### 禁用缓存时
- 每次都创建新的`EmbeddingModel`实例
- 每次都创建新的`LocalHNSWVectorStore`实例
- 适合调试和性能测试
- 确保每次运行都是"干净"的状态

## 性能影响

### 启用缓存
- **首次运行**: 需要初始化缓存，时间稍长
- **后续运行**: 直接使用缓存，时间很短
- **内存使用**: 持续占用内存存储缓存实例

### 禁用缓存
- **每次运行**: 都需要重新初始化，时间较长
- **内存使用**: 每次运行后释放内存
- **调试友好**: 确保每次运行都是独立的状态

## 使用场景

### 启用缓存的场景
- 生产环境
- 需要快速响应的场景
- 多次连续查询
- 资源充足的环境

### 禁用缓存的场景
- 调试和开发
- 性能测试和基准测试
- 内存受限的环境
- 需要确保每次运行都是独立状态

## 注意事项

1. **环境变量优先级**: 环境变量会覆盖默认设置
2. **布尔值解析**: 支持 `true/false`, `1/0`, `True/False` 等格式
3. **进程隔离**: 每次新的进程启动都会重新读取环境变量
4. **性能权衡**: 禁用缓存会显著增加retrieve组件的执行时间

## 示例

```bash
# 测试禁用缓存的情况
$env:RETRIEVE_CACHE_ENABLED="false"
uv run -m datainsight_agent.cli run --question "分析2024年第三季度各渠道用户活跃度变化" --validate

# 测试启用缓存的情况
$env:RETRIEVE_CACHE_ENABLED="true"
uv run -m datainsight_agent.cli run --question "分析2024年第三季度各渠道用户活跃度变化" --validate
```

通过这个环境变量，开发者可以根据需要灵活控制retrieve组件的缓存行为，既保证了生产环境的性能，又提供了调试和测试的便利性。
