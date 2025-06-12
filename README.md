# 📚 LLM4Reading - 智能论文自动化阅读系统

**LLM4Reading** 是一个智能、自动化的学术论文管理工具，旨在帮助研究人员快速追踪最新的arXiv论文，自动生成高质量中文摘要，并进行智能主题分类和高效归档。项目全面集成GitHub Actions，可实现完全自动化的论文检索、摘要生成、文档更新和邮件通知。

## 🚀 项目核心功能

* **自动论文检索**：每日自动搜索arXiv上相关领域最新发布的论文。
* **AI驱动摘要生成**：使用DeepSeek API自动生成精准且高质量的中文摘要。
* **智能主题分类**：将获取的论文自动分类到预设的主题中，如软件测试、代码生成、知识图谱等。
* **自动上传GitHub**：论文摘要自动推送到GitHub仓库。
* **邮件报告系统**：每日自动发送邮件报告，方便快速浏览最新动态。

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

配置文件位于`config/`目录下，包括主配置文件`config.yaml`和敏感信息文件`secrets.env`，具体配置方法请参考[参数配置指南](CONFIGURATION.md)。

* 大模型（LLM）配置

  * `LLM_API_KEY`：大语言模型的API密钥。

* GitHub配置

  * `GH_TOKEN`：用于自动推送论文摘要到GitHub仓库的Personal Access Token。
  * 仓库名称配置：需要填写你配置好的GitHub仓库名。

* 邮件服务配置

  * `EMAIL_PASSWORD`：邮箱服务的SMTP协议应用专用密码。
  * 收件邮箱：用于接收自动生成的论文摘要报告。建议使用Gmail服务进行配置。

### 三、运行测试

```bash
# 测试指定日期范围
python src/main.py --date-range --start-date 2025-06-01 --end-date 2025-06-02

# 默认运行：获取最近1天的论文
python src/main.py

# 仅发送邮件报告
python src/main.py --email-only
```

## 📅 GitHub Actions 在线部署

详细的线上自动部署指南请查看[GitHub Actions 自动化配置指南](GITHUB_ACTIONS_DEPLOYMENT.md)。

## 🚧 常见问题与故障排除

如遇问题，请参考以下常见情况：

* **Secrets配置错误**：请确认Secrets已在GitHub仓库中正确设置。
* **邮件发送失败**：确认使用的是邮箱应用专用密码，并检查SMTP服务器配置。
* **API配额超限**：调整论文获取数量或增加API配额。


## 📝 更多文档与资源

* [参数配置指南](CONFIGURATION.md)
* [GitHub Actions 自动化配置指南](GITHUB_ACTIONS_DEPLOYMENT.md)

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
