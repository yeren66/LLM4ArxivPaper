# GitHub Actions自动化配置指南

项目支持通过GitHub Actions实现全自动运行，配置步骤如下：

### 一、启用Actions功能

- 在你的仓库页面，进入`Actions`选项，启用Actions功能。

### 二、添加GitHub Secrets

在仓库设置 → Secrets and variables → Actions添加以下Secrets：

- `LLM_API_KEY` (AI API密钥)
- `GH_TOKEN` (GitHub访问令牌)
- `EMAIL_PASSWORD` (邮件SMTP密码)

### 三、配置工作流文件

- 将`.github/workflows/daily-paper-crawler.yml`上传到你的仓库中。
- 根据需要修改cron表达式（北京时间为UTC+8）。

```yaml
schedule:
  - cron: '0 19 * * *'  # 每日北京时间凌晨3点
  - cron: '0 0 * * *'   # 每日北京时间上午8点（邮件）
```

### 四、手动运行工作流

- 进入仓库Actions页面 → 点击Run workflow。
- 可选择默认运行、日期范围、仅发送邮件模式。


