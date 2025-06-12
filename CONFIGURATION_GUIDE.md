# 📋 LLM4Reading 配置指南

## 🔧 配置文件说明

### 1. config/config.yaml (主配置文件)
包含所有非敏感的配置信息，可以安全地提交到版本控制。

### 2. config/secrets.env (密钥文件)
包含API密钥等敏感信息，**不要提交到版本控制**。

## ⚙️ 必需的配置修改

### 1. 修改 config/config.yaml

打开 `config/config.yaml` 文件，修改以下配置项：

#### GitHub 配置 (第79-90行)
```yaml
github:
  # 修改为你的GitHub仓库 (格式: 用户名/仓库名)
  repository: "your-username/your-repo-name"
  branch: "main"
  summaries_dir: "summaries"
  commit_message_template: "Add paper summary: {title} (arXiv:{arxiv_id})"
  auto_index: true
  trigger_rtd: true
```

#### LLM 配置 (第57-75行)
```yaml
llm:
  provider: "deepseek"  # 或 "openai"
  model: "deepseek-chat"  # 或 "gpt-4"
  base_url: "https://api.deepseek.com"  # 或 "https://api.openai.com/v1"
  max_tokens: 2000
  temperature: 0.3
  language: "chinese"
```

#### RTD 配置 (第122-131行)
```yaml
rtd:
  # 修改为你的RTD文档URL (可选)
  base_url: "https://your-project.readthedocs.io/zh-cn/latest"
  paper_note_path: "paper_note"
  file_extension: ".html"
  webhook_url: "your_rtd_webhook_url"
  project_name: "your-project-name"
```

#### 邮件配置 (第146-160行)
```yaml
email:
  # 修改为你的邮箱地址
  sender_email: "your-email@example.com"
  recipient_email: "recipient@example.com"
  # 根据你的邮箱提供商选择SMTP服务器
  smtp_server: "smtp.qq.com"      # QQ邮箱
  # smtp_server: "smtp.gmail.com"  # Gmail
  # smtp_server: "smtp.163.com"    # 163邮箱
  smtp_port: 587
  use_tls: true
  send_daily_report: true
  report_time: "08:00"
  include_summary_preview: true
  max_papers_per_topic: 10
  subject_template: "📚 每日论文摘要报告 - {date}"
```

### 2. 创建 config/secrets.env

复制模板文件并填入你的密钥：

```bash
cp config/secrets.env.example config/secrets.env
```

编辑 `config/secrets.env` 文件：

```env
# LLM API 密钥 (支持DeepSeek、OpenAI等)
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# GitHub Personal Access Token (必需)
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 邮箱应用专用密码 (必需)
EMAIL_PASSWORD=abcd efgh ijkl mnop
```

## 🔑 获取API密钥指南

### 1. LLM API 密钥

#### DeepSeek API (推荐，成本低)
1. 访问 [DeepSeek平台](https://platform.deepseek.com/)
2. 注册并登录账户
3. 进入API管理页面
4. 创建新的API密钥
5. 复制密钥（格式：`sk-xxxxxxxx`）

#### OpenAI API (可选)
1. 访问 [OpenAI平台](https://platform.openai.com/)
2. 注册并登录账户
3. 进入API Keys页面
4. 创建新的API密钥
5. 复制密钥（格式：`sk-xxxxxxxx`）

### 2. GitHub Personal Access Token
1. 登录GitHub，点击右上角头像
2. Settings → Developer settings → Personal access tokens → Tokens (classic)
3. Generate new token (classic)
4. 设置Token名称和过期时间
5. 选择权限：
   - ✅ `repo` (Full control of private repositories)
   - ✅ `workflow` (Update GitHub Action workflows)
6. 生成并复制Token（格式：`ghp_xxxxxxxx`）

### 3. 邮箱应用专用密码

#### QQ邮箱
1. 登录QQ邮箱
2. 设置 → 账户 → 开启SMTP服务
3. 生成授权码（16位字符）
4. 使用授权码作为密码

#### Gmail
1. 开启两步验证
2. Google账户设置 → 安全性 → 应用专用密码
3. 生成应用专用密码
4. 使用生成的密码

#### 163邮箱
1. 登录163邮箱
2. 设置 → POP3/SMTP/IMAP
3. 开启SMTP服务
4. 生成授权码

## 📋 配置检查清单

### 必需配置 ✅
- [ ] `config.yaml` 中的 `github.repository`
- [ ] `config.yaml` 中的 `email.sender_email`
- [ ] `config.yaml` 中的 `email.recipient_email`
- [ ] `config.yaml` 中的 `email.smtp_server`
- [ ] `config.yaml` 中的 `llm.provider` 和 `llm.model`
- [ ] `secrets.env` 中的 `LLM_API_KEY`
- [ ] `secrets.env` 中的 `GITHUB_TOKEN`
- [ ] `secrets.env` 中的 `EMAIL_PASSWORD`

### 可选配置 ⚙️
- [ ] `config.yaml` 中的 `rtd.base_url` (如果有RTD文档)
- [ ] `config.yaml` 中的 `arxiv.keyword_groups` (自定义搜索关键词)
- [ ] `config.yaml` 中的 `llm.max_papers` (调整论文数量限制)

## 🔍 配置验证

### 1. 本地测试
```bash
# 测试配置是否正确
python src/main.py --date-range --start-date 2025-06-01 --end-date 2025-06-02
```

### 2. 邮件测试
```bash
# 仅发送邮件测试
python src/main.py --email-only
```

### 3. 检查日志
```bash
# 查看运行日志
tail -f logs/llm4reading.log
```

## ❗ 常见配置错误

### 1. GitHub仓库格式错误
```yaml
# ❌ 错误格式
repository: "my-repo"
repository: "https://github.com/user/repo.git"

# ✅ 正确格式
repository: "username/repo-name"
```

### 2. 邮箱密码错误
```env
# ❌ 使用登录密码
EMAIL_PASSWORD=your_login_password

# ✅ 使用应用专用密码
EMAIL_PASSWORD=abcd efgh ijkl mnop
```

### 3. API密钥格式错误
```env
# ❌ 缺少前缀
LLM_API_KEY=xxxxxxxxxxxxxxxx

# ✅ 包含完整前缀
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
```

## 🚀 配置完成后

1. 推送配置到GitHub：
```bash
git add config/config.yaml
git commit -m "Update configuration"
git push origin main
```

2. 在GitHub仓库设置中添加Secrets
3. 手动触发GitHub Actions测试
4. 检查运行结果和邮件通知

配置完成后，系统将自动每日运行并发送邮件报告！
