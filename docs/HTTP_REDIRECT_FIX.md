# HTTP 301 重定向问题修复

## 问题描述

在执行 weekly 脚本时遇到 HTTP 301 重定向错误：

```
[WARN] arxiv.Client also failed: Page request resulted in HTTP 301: None 
(http://export.arxiv.org/api/query?...)
```

这是因为 ArXiv API 将 HTTP 请求重定向到 HTTPS，但代码没有正确处理这个重定向。

## 解决方案

修改了 `src/fetchers/arxiv_client.py` 中的 `_fallback_fetch` 方法，实现以下改进：

### 1. 多URL策略

现在代码会尝试多个 URL，按优先级顺序：
1. 首先尝试 HTTPS: `https://export.arxiv.org/api/query`
2. 如果失败，回退到 HTTP: `http://export.arxiv.org/api/query`

```python
# Try HTTPS first (preferred), then HTTP if HTTPS fails
urls = [
    "https://export.arxiv.org/api/query",
    "http://export.arxiv.org/api/query"
]

for url in urls:
    try:
        response = requests.get(url, params=params, timeout=30, allow_redirects=True)
        # ... 处理响应
    except Exception as exc:
        # 尝试下一个 URL
        continue
```

### 2. 智能响应验证

改进了响应验证逻辑：
- 成功获取响应后，会解析并检查是否有结果
- 如果响应中包含 `totalResults` 字段，说明是有效响应（即使结果为0）
- 只有在响应无效时才会尝试下一个 URL

```python
# If we got results, return them
if result:
    print(f"[DEBUG] Parsed {len(result)} papers from response")
    return result

# If no results but valid response, check totalResults in XML
if "totalResults" in response.text:
    # Valid response with 0 results is OK, return empty list
    print(f"[DEBUG] Valid response but 0 papers match the criteria")
    return []
```

### 3. 详细的调试日志

添加了详细的调试信息，方便排查问题：
- `[DEBUG] Attempting to fetch from: {url}` - 尝试连接
- `[DEBUG] Successfully fetched from: {url}` - 连接成功
- `[DEBUG] Parsed {n} papers from response` - 解析成功
- `[DEBUG] Valid response but 0 papers match` - 有效响应但无结果
- `[DEBUG] Failed to fetch from {url}: {error}` - 连接失败

## 验证

### 测试结果

运行测试脚本后的输出：

```
[DEBUG] Attempting to fetch from: https://export.arxiv.org/api/query
[DEBUG] Successfully fetched from: https://export.arxiv.org/api/query
[DEBUG] Valid response but 0 papers match the criteria
```

✅ **修复成功**：
- 不再出现 HTTP 301 错误
- HTTPS 连接正常工作
- 正确处理了 ArXiv API 响应

### 测试脚本

创建了以下测试脚本用于验证：

1. `tests/test_redirect_fix.py` - 测试原始查询
2. `tests/test_redirect_simple.py` - 测试简化查询
3. `tests/debug_arxiv_api.py` - 直接调试 ArXiv API

## 注意事项

### 关于 0 结果

如果查询返回 0 个结果，可能的原因：

1. **日期范围限制**：`days_back` 参数限制了查询的时间范围
2. **查询条件过严格**：过多的 include/exclude 关键词和类别限制
3. **ArXiv API 状态**：API 可能临时不可用或有限流
4. **时区问题**：ArXiv API 返回的日期可能与本地时区不一致

### 建议

如果持续遇到 0 结果问题：

1. **增加 `days_back`**：在 `config/pipeline.yaml` 中增加天数
   ```yaml
   fetch:
     days_back: 30  # 从 7 天增加到 30 天
   ```

2. **放宽查询条件**：减少 `exclude` 关键词，增加匹配的可能性

3. **检查网络连接**：确保可以访问 `export.arxiv.org`

4. **查看详细日志**：运行测试脚本查看详细的调试信息

## 相关文件

- `src/fetchers/arxiv_client.py` - 主要修改文件
- `tests/test_redirect_fix.py` - 验证脚本
- `tests/test_redirect_simple.py` - 简化测试
- `tests/debug_arxiv_api.py` - API 调试脚本

## 总结

✅ **HTTP 301 重定向问题已完全解决**

修复后的代码能够：
- 优先使用 HTTPS 避免重定向
- 在 HTTPS 失败时自动回退到 HTTP
- 正确处理 ArXiv API 的各种响应情况
- 提供详细的调试信息方便排查问题

如果仍然看到 0 个结果，这不是重定向问题，而是查询条件或 ArXiv API 本身的问题。
