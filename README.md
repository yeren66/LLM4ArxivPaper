# 📚 LLM4Reading — 面向研究者的 arXiv 智能雷达

LLM4Reading 旨在帮助研究者专注于论文本身：

1. **精准抓取**：用户在 YAML 中定义关心的主题、分类和关键词，系统自动从 arXiv 拉取候选论文。
2. **LLM 筛选**：利用 OpenAI 模型读取摘要，从主题、方法、创新、实验等层面给出综合得分，筛去低相关的内容。
3. **任务驱动总结**：先生成“作为读者想弄明白的问题”列表，再带着这些 TODO 逐项阅读、回答，最终输出结构化 Markdown 报告。
4. **轻量发布**：所有总结统一写入 `site/`，GitHub Actions 自动发布为 GitHub Pages；邮件只发送统计信息与访问链接，让用户快速掌握最新进展。

> ⚠️ 提示：仓库正在逐步重构为上述架构。本 README 和 `config/pipeline.yaml` 描述了新版管线的使用方式；旧的 Read the Docs / GitHub 上传相关模块将被完全移除。

---

## ✨ 特性速览

- 🧭 **主题驱动抓取**：Topic、关键词、排除规则全部由用户配置，每次运行自动生效。
- 🧠 **多维度相关性评分**：LLM 对摘要在多个维度打分并加权求和，≥60 即入选。
- 📋 **TODO 导向阅读**：自动列出想弄清楚的问题，逐条解答后再给综合总结，更贴近实际研究需求。
- 📬 **邮件速览 + 链接**：邮件只包含统计数据、最值得读的论文列表和 GitHub Pages 链接，不打扰却足够全面。
- ☁️ **GitHub Pages 托管**：构建产物与源码分离，用户无需关注发布细节，点击链接即可阅读。

---

## �️ 仓库结构（重构完成后）

```
config/
  pipeline.yaml         # 带详细注释的总配置（可安全地自定义）
requirements.txt
src/
  core/
  fetchers/
  filters/
  summaries/
  publisher/
  workflow/
templates/
  site/                 # GitHub Pages 所需 HTML 模板
site/                   # 构建产物（不提交，Actions 部署到 Pages）
.github/workflows/
  publish.yml           # 自动构建 + 部署 GitHub Pages
```

### 模块职责概览

| 模块 | 职责 |
| --- | --- |
| `core.config_loader` | 解析 `pipeline.yaml`，合并环境变量、校验配置 |
| `fetchers.arxiv_client` | 根据 topic 构造查询，调用 arXiv API（可配置等待时间、最大数量） |
| `filters.relevance_ranker` | 调用 OpenAI，对摘要进行多维度评分和加权 |
| `summaries.task_planner` | 生成 TODO 列表；`summaries.task_reader` 按 TODO 与 LLM 交互并提取答案；`summaries.report_builder` 生成 Markdown |
| `publisher.static_site` | 根据模板批量生成静态页面和索引 |
| `publisher.email_digest` | 汇总统计、发送邮件（可关闭） |
| `workflow.pipeline` | 编排整条流程，支持本地 CLI 和 GitHub Actions |

---

## ⚙️ 配置 `config/pipeline.yaml`

> 我们为每个字段写了详细注释，打开文件即可查看。以下给出关键段落说明：

```yaml
openai:
  api_key: "${OPENAI_API_KEY}"   # 推荐用环境变量注入
  model: "gpt-4o-mini"

fetch:
  days_back: 7                   # 默认抓取过去 7 天
  max_papers_per_topic: 60        # 每个 topic 初始抓取上限

relevance:
  scoring_dimensions:            # 多维度权重结构
    - name: topic_alignment
      weight: 0.35
  pass_threshold: 60

summarization:
  task_list_size: 5
  max_sections: 4

site:
  output_dir: "site"
  base_url: "https://<your-user>.github.io/<your-repo>"

email:
  enabled: true
  sender: "${MAIL_SENDER}"
  recipients:
    - "your-email@example.com"

topics:
  - name: "software_testing"
    label: "软件测试"
    query:
      categories: ["cs.SE", "cs.AI"]
      include_keywords:
        - "software testing"
      exclude_keywords:
        - "quantum"
    interest_prompt: |
      我关注大模型在软件测试中的应用……
```

- **新增/删除 topic**：直接复制节点即可；`name` 会用于输出路径和统计。
- **敏感信息**：带 `${...}` 的配置建议在本地 `.env` 或 GitHub Secrets 中设置。
- **不需要邮件**：将 `email.enabled` 改为 `false`，管线会自动跳过该步骤。

---

## � 快速开始（本地）

```bash
# 1. 准备环境
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 配置环境变量（示例）
export OPENAI_API_KEY="sk-..."
export MAIL_SENDER="bot@example.com"
export MAIL_PASSWORD="app-password"

# 3. 编辑 config/pipeline.yaml
#    - 调整 topic / interest_prompt
#    - 设置 GitHub Pages base_url
#    - 如不需邮件，改 email.enabled 为 false

# 4. 运行一次完整流程（命令即将提供）
python -m workflow.cli run --days-back 7

# 5. 本地预览生成的静态站点
python -m http.server --directory site 8000
```

> `workflow.cli` 会读取配置、下载论文、筛选、总结，并在控制台输出最相关论文的统计摘要。运行结束后，`site/` 目录就是完整的发布内容（同 GitHub Pages）。

---

## ☁️ 使用 GitHub Actions 发布

1. 在仓库设置里新增 Secrets：`OPENAI_API_KEY`、`MAIL_SENDER`、`MAIL_PASSWORD`（如邮件启用）。
2. 将 `config/pipeline.yaml` 中的 `site.base_url` 设置为 `https://<username>.github.io/<repo>`。
3. 推送代码后，`.github/workflows/publish.yml` 会：
   - 安装依赖并执行 `python -m workflow.cli run`；
   - 将 `site/` 作为构建产物上传至 GitHub Pages；
   - （可选）发送邮件摘要。
4. Actions 完成后，访问邮件或终端输出的链接即可查看最新内容。

---

## ❓ 常见问题

| 问题 | 建议排查 |
| --- | --- |
| 抓取不到论文 | 检查 `topics[*].query` 是否过于严格，或提高 `fetch.days_back` |
| LLM 评分耗时长 | 减少 `max_papers_per_topic`，或调低 `runtime.max_concurrency` |
| 邮件发送失败 | 确认 `email.enabled`、SMTP 配置、应用密码是否正确 |
| GitHub Pages 无法访问 | 确认仓库 Settings 中启用了 Pages 且 workflow 正常执行 |

---

## 📝 贡献

欢迎提交 Issue / PR 讨论主题模板、评分 prompt 或总结格式的改进。请在 PR 中说明测试方式与配置变更。

---

## � 许可证

本项目遵循 [MIT License](LICENSE)。
