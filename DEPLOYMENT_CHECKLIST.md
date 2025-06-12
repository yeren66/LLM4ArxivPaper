# GitHub Actions 部署检查清单

## 📋 部署前检查

### 1. 仓库配置
- [ ] Fork或创建新的GitHub仓库
- [ ] 确保仓库是公开的（或有GitHub Pro账户）
- [ ] 启用GitHub Actions功能

### 2. 文件配置
- [ ] 复制 `.github/workflows/daily-paper-crawler.yml` 到你的仓库
- [ ] 修改 `config/config.yaml` 中的仓库名称
- [ ] 确保 `requirements.txt` 包含所有依赖

### 3. API密钥获取

#### LLM API (选择其一)
**DeepSeek API (推荐，成本低)**
- [ ] 注册 [DeepSeek](https://platform.deepseek.com/) 账户
- [ ] 获取API密钥
- [ ] 确认账户有足够余额

**OpenAI API (可选)**
- [ ] 注册 [OpenAI](https://platform.openai.com/) 账户
- [ ] 获取API密钥
- [ ] 确认账户有足够余额

#### GitHub Token
- [ ] 进入 GitHub Settings → Developer settings → Personal access tokens
- [ ] 创建新的Token（Classic）
- [ ] 选择权限：`repo`, `workflow`, `write:packages`
- [ ] 复制Token（只显示一次）

#### 邮箱配置
- [ ] 开启邮箱的SMTP服务
- [ ] 获取应用专用密码（不是登录密码）
- [ ] 记录SMTP服务器地址和端口

### 4. GitHub Secrets配置
进入仓库 Settings → Secrets and variables → Actions

- [ ] 添加 `LLM_API_KEY`
- [ ] 添加 `GH_TOKEN`
- [ ] 添加 `EMAIL_PASSWORD`

### 5. 配置文件修改

#### config/config.yaml
```yaml
github:
  repository: "your-username/your-repo-name"  # 修改为你的仓库

email:
  sender_email: "your-email@example.com"      # 修改为你的邮箱
  recipient_email: "recipient@example.com"   # 修改为接收邮箱

rtd:
  base_url: "https://your-project.readthedocs.io/zh-cn/latest/"  # 可选
```

## 🚀 部署步骤

### 1. 推送代码
```bash
git add .
git commit -m "Setup GitHub Actions for automated paper crawling"
git push origin main
```

### 2. 测试手动运行
- [ ] 进入 GitHub Actions 页面
- [ ] 选择 "Daily Paper Crawler" 工作流
- [ ] 点击 "Run workflow"
- [ ] 选择测试参数运行

### 3. 检查运行结果
- [ ] 查看Actions运行日志
- [ ] 确认论文文件已上传到仓库
- [ ] 检查邮件是否正常发送
- [ ] 验证RTD文档是否更新

## ✅ 验证清单

### 功能验证
- [ ] arXiv论文搜索正常
- [ ] LLM摘要生成成功
- [ ] 文件按主题正确分类
- [ ] GitHub自动上传成功
- [ ] 邮件通知正常发送

### 定时任务验证
- [ ] 等待第二天自动运行
- [ ] 检查是否按时执行
- [ ] 验证新论文是否被处理

## 🔧 故障排除

### 常见错误
1. **Secrets未配置**
   - 错误：`KeyError: 'LLM_API_KEY'` 或 `KeyError: 'GH_TOKEN'`
   - 解决：检查GitHub Secrets配置

2. **权限不足**
   - 错误：`403 Forbidden`
   - 解决：检查GitHub Token权限

3. **邮件发送失败**
   - 错误：`Authentication failed`
   - 解决：使用应用专用密码

4. **API配额超限**
   - 错误：`Rate limit exceeded`
   - 解决：减少论文数量或等待重置

### 调试技巧
- 查看Actions运行日志
- 使用手动触发测试
- 检查配置文件格式
- 验证API密钥有效性

## 📞 获取帮助

如果遇到问题：
1. 查看项目README.md的故障排除部分
2. 检查GitHub Actions的运行日志
3. 在项目Issues中搜索相似问题
4. 创建新的Issue描述问题

## 🎯 成功标志

当看到以下情况时，说明部署成功：
- ✅ GitHub Actions显示绿色勾号
- ✅ 仓库中出现新的论文文件
- ✅ 收到邮件通知
- ✅ RTD文档自动更新

恭喜！你的自动化论文阅读系统已经成功部署！🎉
