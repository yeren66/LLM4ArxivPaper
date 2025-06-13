# 📚 LLM4Reading - 智能论文自动化阅读系统

**LLM4Reading** 是一个智能、自动化的学术论文管理工具，旨在帮助研究人员快速追踪最新的arXiv论文，自动生成高质量中文摘要，并进行智能主题分类和高效归档。项目全面集成GitHub Actions，可实现完全自动化的论文检索、摘要生成、文档更新和邮件通知。

## 🚀 项目核心功能

* **自动论文检索**：每周自动搜索arXiv上相关领域最新发布的论文。
* **AI驱动摘要生成**：使用DeepSeek API自动生成精准且高质量的中文摘要。
* **智能主题分类**：将获取的论文自动分类到预设的主题中，如软件测试、代码生成、知识图谱等。
* **自动上传GitHub**：RTD文档结构自动推送到GitHub仓库（本地摘要文件不上传）。
* **邮件报告系统**：每周自动发送邮件报告，方便快速浏览最新动态。

> **注意**：本项目不集成自动构建文档功能（如Razor Docs）。如果你有此需求，请参考专门构建[Razor Docs 文档](https://razordocs.com)以及[Razor Docs GitHub项目](https://github.com/razordocs/razor-docs)。

## 🛠️ 技术栈与核心架构

项目使用Python 3.9+ 开发，核心技术包括：

* **arXiv API**: 论文检索与获取。
* **DeepSeek/OpenAI API**: 摘要生成。
* **GitHub Actions**: 自动化构建和运行任务。
* **SMTP邮件服务**: 发送自动化邮件通知。

## 🔍 快速上手指南

### 一、环境准备

```bash
# 克隆项目
git clone https://github.com/your-username/LLM4Reading.git
cd LLM4Reading

# 安装依赖
pip install -r requirements.txt
```

### 二、关键配置

配置文件位于`config/`目录下，包括主配置文件`config.yaml`和敏感信息文件`secrets.env`。

## 📁 项目结构

```
LLM4Reading/
├── src/                          # 核心源代码
│   ├── main.py                   # 主程序入口
│   ├── paper_fetcher/            # 论文获取模块
│   ├── llm_summarizer/           # LLM摘要生成模块
│   ├── topic_manager/            # 主题分类管理模块
│   ├── github_uploader/          # GitHub上传模块
│   └── email_notifier/           # 邮件通知模块
├── config/                       # 配置文件
│   ├── config.yaml              # 主配置文件
│   └── secrets.env              # 密钥配置文件
├── summaries/                    # 本地论文摘要存储（不上传到GitHub）
├── source/paper_note/           # RTD文档源文件（上传到GitHub）
├── logs/                        # 日志文件
├── .github/workflows/           # GitHub Actions工作流
└── requirements.txt             # Python依赖
```

## 📝 文件命名规则

- **本地摘要文件**: `summaries/{YYYYMMDD}_{arxiv_id}.md`
- **RTD文档文件**: `source/paper_note/{topic}/{YYYYMMDD}_{arxiv_id}.md`
- **GitHub上传**: 仅上传RTD文档结构，本地summaries目录保持本地存储

* 大模型（LLM）配置

  * `LLM_API_KEY`：大语言模型的API密钥。

* GitHub配置

  * `GH_TOKEN`：用于自动推送论文摘要到GitHub仓库的Personal Access Token。
  * 仓库名称配置：需要填写你配置好的GitHub仓库名。

* 邮件服务配置

  * `EMAIL_PASSWORD`：邮箱服务的SMTP协议应用专用密码。
  * 收件邮箱：用于接收自动生成的论文摘要报告。建议使用Gmail服务进行配置。

### 三、运行测试

#### 🔧 使用方式

```bash
# 1. 默认运行（获取上周论文 + 发送邮件）- 推荐
python src/main.py

# 2. 只获取论文，不发送邮件
python src/main.py --no-email

# 3. 指定日期范围获取论文
python src/main.py --date-range --start-date 2025-06-01 --end-date 2025-06-07

# 4. 指定日期范围，不发送邮件
python src/main.py --date-range --start-date 2025-06-01 --end-date 2025-06-07 --no-email
```

#### 📋 src/main.py 参数说明

| 参数 | 作用 |
|------|------|
| `--date-range` | 指定日期范围模式 |
| `--start-date` | 开始日期 (YYYY-MM-DD) |
| `--end-date` | 结束日期 (YYYY-MM-DD) |
| `--no-email` | 禁用邮件通知 |

## 📅 GitHub Actions 自动化部署

项目已配置GitHub Actions工作流，支持：
- 每周一自动运行论文爬取和摘要生成
- 自动上传RTD文档结构到GitHub
- 自动发送邮件报告

配置GitHub Secrets：
- `LLM_API_KEY`: DeepSeek API密钥
- `LLM_BASE_URL`: DeepSeek API地址
- `GH_TOKEN`: GitHub Personal Access Token
- `EMAIL_PASSWORD`: 邮箱SMTP密码

## 🚧 常见问题与故障排除

如遇问题，请参考以下常见情况：

* **Secrets配置错误**：请确认Secrets已在GitHub仓库中正确设置。
* **邮件发送失败**：确认使用的是邮箱应用专用密码，并检查SMTP服务器配置。
* **API配额超限**：调整论文获取数量或增加API配额。


## 📝 配置说明

主要配置项说明：
- `config/config.yaml`: 主配置文件，包含arXiv搜索关键词、邮件设置等
- `config/secrets.env`: 敏感信息配置，包含API密钥、邮箱密码等

## 🎯 最佳使用实践

* 定期监控API使用情况。
* 根据研究方向及时更新搜索关键词。
* 检查邮件报告，确保系统正常运行。
* 定期进行配置备份。

## 🤝 贡献和支持

本项目开源且接受社区贡献，欢迎通过提交Issues或Pull Requests参与项目维护。

## 📜 许可证

本项目遵循MIT许可证，详细信息参见[LICENSE文件](LICENSE)。

---

📖 **文档网站**：[ReadTheDocs在线文档](https://docs.readthedocs.com/platform/stable/)
