# test — 运行测试

description: 运行 pytest 测试套件，可选按关键字过滤

# arguments

- `[pattern]` (可选): pytest 关键字过滤模式

# 描述

运行项目测试套件。

等价于：

```bash
pytest tests/ -v -k "<pattern>"
```

# 示例

```
/test                    # 运行全部测试
/test regression         # 只运行回归相关测试
/test did                # 只运行 DID 相关测试
/test data_fetcher       # 只运行数据获取测试
/test checkpoint         # 只运行断点续传测试
/test -k "did or iv"    # 运行 DID 或 IV 测试
```

# 测试覆盖

| 测试文件 | 覆盖范围 |
|---------|---------|
| `tests/test_checkpoint.py` | 断点续传管理 |
| `tests/test_event_monitor.py` | 事件监控系统 |
| `tests/test_demo_research_report.py` | 研报生成流水线 |
| `tests/test_llm_gateway.py` | LLM 网关与路由 |
| `tests/test_ollama_provider.py` | Ollama 本地模型 |
| `tests/test_econometrics.py` | 计量经济学方法 |
| `tests/test_data_cache.py` | 数据缓存 |
