# LLM4Reading - 智能论文阅读系统

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Enabled-brightgreen.svg)](/.github/workflows)

一个全自动的学术论文阅读系统，能够搜索arXiv论文、获取详细内容、生成中文摘要，并自动发布到RTD文档网站。

## 🚀 核心功能

- **智能论文搜索**：基于关键词组的arXiv论文搜索，支持多主题分类
- **深度内容提取**：获取论文完整HTML内容，提供丰富的上下文信息
- **AI智能摘要**：使用DeepSeek API生成高质量中文论文摘要
- **自动文档发布**：按主题分类上传到GitHub，自动生成RTD文档
- **邮件通知系统**：每日自动发送论文摘要报告
- **GitHub Actions集成**：支持每日定时运行和手动触发

## 📋 系统架构

```
LLM4Reading/
├── src/                          # 核心源代码
│   ├── main.py                   # 主程序入口
│   ├── paper_fetcher/            # 论文获取模块
│   │   ├── arxiv_crawler.py      # arXiv搜索爬虫
│   │   └── ar5iv_parser.py       # 论文内容解析器
│   ├── llm_summarizer/           # LLM摘要生成模块
│   │   └── openai_summarizer.py  # DeepSeek API集成
│   ├── topic_manager/            # 主题管理模块
│   │   └── topic_organizer.py    # 论文主题分类器
│   ├── github_uploader/          # GitHub上传模块
│   │   └── github_client.py      # GitHub API客户端
│   └── email_notifier/           # 邮件通知模块
│       └── email_sender.py       # 邮件发送器
├── config/                       # 配置文件
│   ├── config.yaml              # 主配置文件
│   ├── secrets.env              # 密钥配置文件
│   └── secrets.env.example      # 密钥配置模板
├── source/paper_note/           # RTD文档源文件
└── summaries/                   # 本地摘要文件存储
```

## 🛠️ 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/your-username/LLM4Reading.git
cd LLM4Reading

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置设置

#### 复制配置模板
```bash
cp config/secrets.env.example config/secrets.env
```

#### 编辑密钥配置 (`config/secrets.env`)
```env
# DeepSeek API配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# GitHub配置
GITHUB_TOKEN=your_github_token_here

# 邮件配置
EMAIL_PASSWORD=your_email_app_password_here
```

#### 编辑主配置 (`config/config.yaml`)
```yaml
# GitHub仓库配置
github:
  repository: "your-username/your-repo-name"
  
# 邮件配置
email:
  sender_email: "your-email@example.com"
  recipient_email: "recipient@example.com"
  
# RTD配置
rtd:
  base_url: "https://your-project.readthedocs.io/zh-cn/latest/"
```

### 3. 运行测试

```bash
# 测试指定日期范围的论文获取
python src/main.py --date-range --start-date 2025-06-01 --end-date 2025-06-02

# 获取最近1天的论文
python src/main.py

# 手动触发邮件报告
python src/main.py --email-only
```

## 📊 搜索配置

系统支持按关键词组进行精确搜索，当前配置的主题包括：

### 关键词组配置
- **test_generation**: 测试生成相关论文
- **software_testing**: 软件测试相关论文  
- **code_generation**: 代码生成相关论文
- **code_knowledge_graph**: 代码知识图谱相关论文

### arXiv分类覆盖
- `cs.AI`: 人工智能
- `cs.SE`: 软件工程
- `cs.CL`: 计算语言学
- `cs.LG`: 机器学习
- `cs.PL`: 编程语言

## 📁 输出格式

### 文件命名
- 格式：`YYYYMMDD_arXivID.md`
- 示例：`20250612_2506.01059.md`

### 文件内容格式
```markdown
# 250601_论文标题

---
**论文信息**

- **标题**: 论文完整标题
- **arXiv ID**: 2506.01059
- **作者**: 作者1, 作者2, 作者3
- **发表日期**: 2025-06-01T22:29:32+00:00
- **论文链接**: [2506.01059](https://arxiv.org/abs/2506.01059)
- **总结生成时间**: 2025-06-12 22:17:32

---

[DeepSeek生成的中文摘要内容]
```

### 目录结构
```
source/paper_note/
├── index.rst                    # 主索引
├── test_generation/             # 测试生成主题
│   ├── index.rst
│   └── 20250612_2506.01059.md
├── software_testing/            # 软件测试主题
│   ├── index.rst
│   └── 20250612_2506.01199.md
├── code_generation/             # 代码生成主题
└── knowledge_graph/             # 知识图谱主题
```

## 🔧 高级配置

### 搜索策略配置
```yaml
arxiv:
  search_strategy:
    separate_keyword_searches: true    # 为每个关键词组单独搜索
    use_phrase_search: true           # 使用引号包围短语搜索
    max_results_per_group: 20         # 每个关键词组的最大结果数
```

### 相关性过滤
- 最低相关性分数：0.05
- 基于标题和摘要的关键词匹配
- 支持按关键词组的精确相关性计算

## 🤖 GitHub Actions 自动化部署

### 功能特性

系统支持完全自动化运行：

- **每日定时运行**：凌晨3点自动获取前一天的论文
- **邮件报告**：上午8点发送每日摘要报告
- **手动触发**：支持自定义日期范围的手动执行

### 部署步骤

#### 1. 创建GitHub Actions工作流

在你的仓库中创建 `.github/workflows/daily-paper-crawler.yml` 文件：

```yaml
name: Daily Paper Crawler

on:
  # 每日凌晨3点自动运行
  schedule:
    - cron: '0 3 * * *'  # UTC时间，对应北京时间11点

  # 支持手动触发
  workflow_dispatch:
    inputs:
      start_date:
        description: '开始日期 (YYYY-MM-DD)'
        required: false
        default: ''
      end_date:
        description: '结束日期 (YYYY-MM-DD)'
        required: false
        default: ''
      email_only:
        description: '仅发送邮件报告'
        required: false
        default: 'false'
        type: boolean

jobs:
  crawl-papers:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout repository
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt

    - name: Create secrets.env
      run: |
        echo "DEEPSEEK_API_KEY=${{ secrets.DEEPSEEK_API_KEY }}" >> config/secrets.env
        echo "GITHUB_TOKEN=${{ secrets.GITHUB_TOKEN }}" >> config/secrets.env
        echo "EMAIL_PASSWORD=${{ secrets.EMAIL_PASSWORD }}" >> config/secrets.env

    - name: Run daily crawler
      run: |
        if [ "${{ github.event.inputs.email_only }}" = "true" ]; then
          python src/main.py --email-only
        elif [ -n "${{ github.event.inputs.start_date }}" ] && [ -n "${{ github.event.inputs.end_date }}" ]; then
          python src/main.py --date-range --start-date "${{ github.event.inputs.start_date }}" --end-date "${{ github.event.inputs.end_date }}"
        else
          python src/main.py
        fi
```

#### 2. 配置GitHub Secrets

在GitHub仓库设置中添加以下Secrets：

**Settings → Secrets and variables → Actions → New repository secret**

| Secret名称 | 说明 | 示例值 |
|-----------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API密钥 | `sk-xxxxxxxxxxxxxxxx` |
| `GITHUB_TOKEN` | GitHub访问令牌 | `ghp_xxxxxxxxxxxxxxxx` |
| `EMAIL_PASSWORD` | 邮箱应用专用密码 | `abcd efgh ijkl mnop` |

#### 3. GitHub Token权限配置

创建GitHub Personal Access Token时需要以下权限：

- **Repository permissions**:
  - Contents: Read and write
  - Metadata: Read
  - Pull requests: Read and write

- **Account permissions**:
  - Email addresses: Read

#### 4. 邮件配置说明

**QQ邮箱配置示例**：
1. 登录QQ邮箱 → 设置 → 账户
2. 开启SMTP服务，获取授权码
3. 在 `config/config.yaml` 中配置：
```yaml
email:
  smtp_server: "smtp.qq.com"
  smtp_port: 587
  sender_email: "your-email@qq.com"
  recipient_email: "recipient@qq.com"
```

**Gmail配置示例**：
1. 开启两步验证
2. 生成应用专用密码
3. 配置SMTP服务器为 `smtp.gmail.com:587`

### 使用方法

#### 自动运行
- 系统会在每天凌晨3点（UTC时间）自动运行
- 自动获取前一天发布的论文
- 生成摘要并上传到GitHub
- 发送邮件报告

#### 手动触发
1. 进入GitHub仓库页面
2. 点击 **Actions** 标签
3. 选择 **Daily Paper Crawler** 工作流
4. 点击 **Run workflow** 按钮
5. 可选择：
   - **默认运行**：获取最近1天的论文
   - **指定日期范围**：输入开始和结束日期
   - **仅发送邮件**：只发送现有论文的摘要报告

#### 监控和调试
- 在Actions页面查看运行日志
- 检查每个步骤的执行状态
- 查看错误信息和调试输出

### 高级配置

#### 自定义运行时间
修改 `.github/workflows/daily-paper-crawler.yml` 中的cron表达式：

```yaml
schedule:
  - cron: '0 19 * * *'  # UTC 19:00 = 北京时间 03:00
  - cron: '0 0 * * *'   # UTC 00:00 = 北京时间 08:00 (邮件报告)
```

#### 多时区支持
```yaml
# 为不同时区创建多个任务
- cron: '0 3 * * *'   # 欧洲时间
- cron: '0 11 * * *'  # 亚洲时间
- cron: '0 19 * * *'  # 美洲时间
```

#### 错误通知
添加失败通知到工作流：

```yaml
- name: Notify on failure
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: failure
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### 最佳实践

#### 1. 安全配置
- **永远不要**在代码中硬编码API密钥
- 使用GitHub Secrets存储敏感信息
- 定期轮换API密钥和Token
- 限制GitHub Token的最小权限

#### 2. 性能优化
- 使用缓存加速依赖安装
- 合理设置论文数量限制
- 避免在高峰时段运行
- 监控API调用频率

#### 3. 可靠性保障
- 设置合理的超时时间
- 添加重试机制
- 保存运行日志
- 监控工作流状态

#### 4. 成本控制
- 监控API使用量
- 设置合理的运行频率
- 使用免费的GitHub Actions额度
- 优化代码减少运行时间

### 示例配置文件

完整的 `.github/workflows/daily-paper-crawler.yml` 文件已包含在项目中，包含：
- 自动定时运行
- 手动触发选项
- 错误处理和通知
- 日志上传和保存
- 缓存优化

### 📋 快速部署指南

详细的部署步骤和检查清单请参考：[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

该文档包含：
- 完整的部署前检查清单
- 逐步部署指导
- 常见问题解决方案
- 成功验证标准

## 📧 邮件通知

每日邮件报告包含：
- 论文数量统计
- 按主题分类的论文列表
- RTD文档链接
- 论文摘要预览

## 🔍 故障排除

### 常见问题

#### 1. API相关问题
- **DeepSeek API配额限制**
  - 检查API密钥是否有效
  - 合理设置`max_papers`参数
  - 监控每日调用次数

- **GitHub API限制**
  - 确保Token有足够权限
  - 检查仓库名称配置
  - 避免频繁上传大文件

#### 2. GitHub Actions问题
- **Secrets配置错误**
  ```bash
  # 检查Secrets是否正确设置
  echo "DEEPSEEK_API_KEY length: ${#DEEPSEEK_API_KEY}"
  echo "GITHUB_TOKEN length: ${#GITHUB_TOKEN}"
  ```

- **工作流权限不足**
  - 确保仓库开启Actions权限
  - 检查Token的Repository权限
  - 验证GITHUB_TOKEN的Contents权限

- **定时任务不执行**
  - GitHub Actions在仓库不活跃时可能暂停
  - 手动触发一次工作流重新激活
  - 检查cron表达式是否正确

#### 3. 邮件发送问题
- **SMTP认证失败**
  - 使用应用专用密码而非账户密码
  - 检查SMTP服务器和端口配置
  - 确认邮箱开启了SMTP服务

- **邮件内容为空**
  - 检查是否有论文数据
  - 验证模板文件是否存在
  - 查看邮件发送日志

#### 4. 论文获取问题
- **arXiv API超时**
  - 增加请求延迟时间
  - 检查网络连接
  - 使用代理服务器（如需要）

- **相关性过滤过严**
  - 降低`min_score`阈值
  - 检查关键词配置
  - 验证分类逻辑

### 日志查看

#### 本地运行
```bash
# 查看实时日志
tail -f logs/llm4reading.log

# 查看错误日志
grep "ERROR" logs/llm4reading.log

# 查看特定日期的日志
grep "2025-06-12" logs/llm4reading.log
```

#### GitHub Actions
```bash
# 在Actions页面查看：
# 1. 进入仓库 → Actions
# 2. 选择失败的工作流
# 3. 点击失败的作业
# 4. 展开失败的步骤查看详细日志
```

### 调试模式

#### 启用详细日志
在 `config/config.yaml` 中设置：
```yaml
logging:
  level: "DEBUG"
  console_output: true
```

#### 测试单个组件
```bash
# 测试arXiv搜索
python -c "from src.paper_fetcher.arxiv_crawler import ArxivCrawler; print('OK')"

# 测试LLM摘要
python -c "from src.llm_summarizer.openai_summarizer import OpenAISummarizer; print('OK')"

# 测试GitHub上传
python -c "from src.github_uploader.github_client import GitHubClient; print('OK')"
```

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目！

## 📞 联系方式

如有问题或建议，请通过GitHub Issues联系。

---

**文档网站**: https://your-project.readthedocs.io/zh-cn/latest/
