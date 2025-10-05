# GitHub Pages 部署指南

## 架构概览

本项目使用 GitHub Actions 自动生成静态站点并部署到 GitHub Pages。

### 站点结构

```
site/
├── index.html              # 首页：按主题列出所有论文
├── manifest.json           # 元数据（base_url、topics、生成时间）
└── topics/
    ├── software_testing/   # 每个主题一个目录
    │   ├── 2506.xxxxx.html
    │   └── 2506.yyyyy.html
    └── code_generation/
        └── 2506.zzzzz.html
```

每篇论文页面包含：
- 标题、作者、arXiv 链接
- 相关性评分
- 阅读 TODO 列表
- 逐项问答
- 综合总结

---

## 部署步骤

### 1. 启用 GitHub Pages

1. 进入仓库 → **Settings** → **Pages**
2. **Source** 选择: **GitHub Actions** (⚠️ 不是 "Deploy from a branch")
3. 保存

### 2. 配置自动部署（可选）

#### 方式 A: 设置仓库变量（推荐）

1. Settings → Secrets and variables → Actions → **Variables** 标签
2. 点击 **New repository variable**
3. 添加:
   - Name: `ENABLE_PAGES_DEPLOY`
   - Value: `true`

#### 方式 B: 修改工作流默认值

编辑 `.github/workflows/pipeline-smoke.yml`:

```yaml
env:
  ENABLE_PAGES_DEPLOY: 'true'  # 改为 true
```

### 3. 触发部署

#### 自动触发（已配置）
- 每周一 UTC 3:00（北京时间 11:00）自动运行

#### 手动触发
1. 进入 Actions → **Pipeline Smoke Test**
2. 点击 **Run workflow**
3. 保持默认参数或调整 mode/topic_limit
4. 点击 **Run workflow** 按钮

### 4. 查看部署状态

1. Actions 页面查看工作流运行状态
2. 成功后访问: `https://<username>.github.io/LLM4ArxivPaper`
   - 当前应为: `https://yeren66.github.io/LLM4ArxivPaper`

---

## 本地预览

### 生成站点

```bash
# 安装依赖
pip install -r requirements.txt

# 生成站点（离线模式，不调用 OpenAI）
python -m src.main \
  --config config/pipeline.yaml \
  --mode offline \
  --topic-limit 1 \
  --paper-limit 3 \
  --no-email

# 检查生成的文件
ls -R site/
```

### 预览 HTML

```bash
# macOS
open site/index.html

# Linux
xdg-open site/index.html

# 或使用 Python 启动本地服务器
cd site && python -m http.server 8000
# 浏览器访问 http://localhost:8000
```

---

## CI/CD 工作流说明

### 工作流文件

`.github/workflows/pipeline-smoke.yml`

### 关键步骤

1. **Run pipeline** - 执行论文抓取、评分、总结
2. **Upload static site artifact** - 上传 `site/` 目录为 artifact（总是执行）
3. **Deploy to GitHub Pages** - 部署到 Pages（需启用 `ENABLE_PAGES_DEPLOY`）

### Artifact 下载

即使未启用自动部署，也可以下载预览：

1. Actions → 选择某次运行
2. 下拉到 **Artifacts** 部分
3. 下载 `site-preview.zip`
4. 解压后本地打开 `index.html`

---

## 配置说明

### Base URL

在 `config/pipeline.yaml` 中设置：

```yaml
site:
  output_dir: "site"
  base_url: "https://yeren66.github.io/LLM4ArxivPaper"
```

- 本地预览时可留空或设为相对路径
- 部署到 Pages 时必须设置为完整 URL，确保邮件和链接正确

### 邮件集成

站点 URL 会自动包含在邮件摘要中：

```yaml
email:
  enabled: true
  # ...
```

邮件会包含：
- 论文数量统计
- 按主题分组的论文列表
- 每篇论文链接到对应的 HTML 页面

---

## 自定义域名（可选）

### 1. DNS 设置

在域名提供商处添加 CNAME 记录：

```
papers.yourdomain.com  →  <username>.github.io
```

### 2. GitHub 配置

1. Settings → Pages → Custom domain
2. 输入: `papers.yourdomain.com`
3. 勾选 **Enforce HTTPS**

### 3. 更新配置

修改 `config/pipeline.yaml`:

```yaml
site:
  base_url: "https://papers.yourdomain.com"
```

---

## 故障排查

### 部署失败

**症状**: Actions 运行成功但无法访问站点

**检查**:
1. Settings → Pages → Source 是否设为 **GitHub Actions**
2. 工作流权限: `pages: write` 和 `id-token: write`
3. `ENABLE_PAGES_DEPLOY` 是否设为 `true`

### 404 错误

**症状**: 访问 `<username>.github.io/LLM4ArxivPaper` 显示 404

**原因**:
- 首次部署需要 1-2 分钟生效
- 仓库名称大小写敏感

**解决**:
- 等待几分钟后刷新
- 确认 URL 拼写正确

### 样式错误

**症状**: 页面显示但样式混乱

**原因**: `base_url` 配置不正确

**解决**:
```yaml
# 确保 base_url 与实际部署地址匹配
site:
  base_url: "https://yeren66.github.io/LLM4ArxivPaper"
```

### 站点内容过旧

**症状**: 站点未显示最新论文

**原因**:
- 工作流未自动触发
- 相关性评分过低，论文被过滤

**解决**:
- 手动触发工作流
- 调整 `relevance.pass_threshold` 降低阈值
- 检查 Actions 日志中的 `papers_selected` 数量

---

## 维护建议

### 定期检查

- 每周检查 Actions 运行状态
- 确认邮件摘要收到且链接有效
- 查看 artifact 下载量（如果公开）

### 性能优化

- 控制 `fetch.max_papers_per_topic` 避免站点过大
- 定期清理旧论文（可写脚本归档）
- 考虑添加 CDN（如 Cloudflare）

### 安全注意

- ⚠️ 不要在配置中明文存储密码
- 使用 GitHub Secrets 管理敏感信息
- 定期更新 GitHub Actions 版本

---

## 相关资源

- [GitHub Pages 官方文档](https://docs.github.com/pages)
- [GitHub Actions 部署文档](https://docs.github.com/actions/deployment/about-deployments/deploying-with-github-actions)
- [arXiv API 文档](https://info.arxiv.org/help/api/index.html)
