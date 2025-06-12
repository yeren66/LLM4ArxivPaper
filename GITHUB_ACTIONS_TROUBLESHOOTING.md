# 🔧 GitHub Actions 故障排除指南

## 问题描述

GitHub Actions工作流执行成功，但没有看到预期的行为：
- ❌ 设置了日期范围（6.3~6.4）但执行了email模式
- ❌ 没有爬取新论文
- ❌ 没有生成LLM总结
- ❌ 没有上传到GitHub仓库

## 🚨 根本原因

从日志分析发现：
```
case "email" in
Running email-only mode...
Generating email report for 2025-06-11
Found 0 summaries for 2025-06-11
```

**问题**：即使设置了日期范围，工作流仍然执行了`email`模式而不是`date_range`模式。

## 🔍 问题诊断

### 1. GitHub Actions逻辑判断错误

**原始问题**：工作流的条件判断顺序和逻辑有误，导致即使设置了日期范围也执行了错误的模式。

**修复前的逻辑**：
```bash
# 错误的逻辑顺序
if [ schedule ]; then
  # 处理定时任务
elif [ email_only = true ]; then
  # 处理邮件模式
elif [ start_date && end_date ]; then
  # 处理日期范围 - 这个条件可能没有正确触发
```

**修复后的逻辑**：
```bash
# 正确的逻辑顺序 - 日期范围优先
if [ start_date && end_date ]; then
  # 处理日期范围 - 最高优先级
elif [ email_only = true ]; then
  # 处理邮件模式
elif [ schedule ]; then
  # 处理定时任务
```

### 2. GitHub Actions执行模式

| 模式 | 触发条件 | 执行命令 | 预期行为 |
|------|----------|----------|----------|
| `date_range` | 手动设置开始和结束日期 | `python src/main.py --date-range --start-date X --end-date Y` | 爬取指定日期范围的论文 |
| `email` | 手动设置email_only=true 或 定时任务(UTC 00:00) | `python src/main.py --email-only` | 仅发送邮件报告 |
| `crawl` | 其他情况（默认） | `python src/main.py --daily --days-back 1` | 爬取最近1天的论文 |

### 2. 常见问题

#### 问题1：执行了错误的模式
**症状**：工作流成功但没有爬取论文
**原因**：可能执行了`email`模式而不是`crawl`模式
**解决**：检查GitHub Actions日志中的"Determine run type"步骤

#### 问题2：API密钥未设置
**症状**：初始化失败或API调用失败
**原因**：GitHub Secrets中缺少必要的API密钥
**解决**：确保设置了以下Secrets：
- `LLM_API_KEY` - LLM API密钥
- `GH_TOKEN` - GitHub Personal Access Token
- `EMAIL_PASSWORD` - 邮箱应用专用密码

#### 问题3：没有找到相关论文
**症状**：工作流成功但显示"No papers to process"
**原因**：关键词搜索没有找到相关论文
**解决**：检查`config/config.yaml`中的关键词配置

## 🛠️ 修复方案

### 1. 更新GitHub Actions工作流

已修复的工作流确保：
- 正确判断执行模式
- 默认执行完整的爬取流程
- 提供详细的调试信息

### 2. 本地测试工具

使用以下脚本进行本地测试：

```bash
# 测试完整工作流
python debug_workflow.py

# 测试GitHub Actions行为
python test_github_actions.py

# 测试OpenAI修复
python test_openai_fix.py
```

### 3. 手动触发测试

在GitHub仓库中：
1. 进入 Actions 标签页
2. 选择 "Daily Paper Crawler"
3. 点击 "Run workflow"
4. 设置参数：
   - 如果要测试完整流程：不设置任何参数（使用默认）
   - 如果要测试特定日期：设置start_date和end_date
   - 如果只要测试邮件：设置email_only=true

## 🔍 调试步骤

### 步骤1：检查GitHub Actions日志

1. 进入GitHub仓库的Actions页面
2. 点击最近的工作流运行
3. 查看"Run paper crawler"步骤的输出
4. 确认执行的是哪种模式

### 步骤2：检查环境变量

在GitHub Actions日志中查找：
```
Event name: workflow_dispatch
Email only: false
Start date: 
End date: 
Default crawl mode (manual trigger or fallback)
```

### 步骤3：检查API调用

查找以下日志信息：
- `ArxivCrawler initialized with X keyword groups`
- `Found X papers for keywords`
- `LLM client configured successfully`
- `Successfully generated X summaries`
- `GitHubClient initialized for username/repo`

### 步骤4：检查文件生成

工作流应该生成以下文件：
- `logs/llm4reading.log` - 详细日志
- `summaries/*.md` - 论文总结文件
- `source/paper_note/*/` - 按主题组织的文件

## ✅ 验证修复

修复后，GitHub Actions日志应该显示：

```
Default crawl mode (manual trigger or fallback)
Running daily crawl mode...
This will: 1) Crawl arXiv papers, 2) Generate LLM summaries, 3) Upload to GitHub
Starting LLM4Reading daily run - processing last 1 days...
ArxivCrawler initialized with 4 keyword groups (20 total keywords) and 5 categories
Found X papers to process for daily run (1 days):
1. Paper Title (arXiv:XXXX.XXXXX)
...
Generating LLM summaries...
LLM client configured successfully for provider: deepseek
Successfully generated X summaries out of X papers
Organizing papers by topics...
Uploading all summaries to GitHub...
Daily run (1 days) completed successfully - processed X papers
```

## 🚨 如果仍然有问题

1. **检查配置文件**：确保`config/config.yaml`中的GitHub仓库配置正确
2. **检查权限**：确保GitHub Token有足够的权限（repo, workflow）
3. **检查网络**：确保GitHub Actions环境能访问arXiv和LLM API
4. **查看完整日志**：下载GitHub Actions的完整日志文件进行分析

## 📞 获取帮助

如果问题仍然存在，请提供：
1. GitHub Actions的完整日志
2. `config/config.yaml`文件内容（隐藏敏感信息）
3. 本地测试脚本的输出结果
