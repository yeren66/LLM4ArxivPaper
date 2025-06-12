# 🔄 环境变量名称变更说明

## 📋 变更概述

为了符合GitHub Actions的规范和提高配置的通用性，我们对环境变量名称进行了以下变更：

## 🔧 变更详情

### 1. GitHub Token变量名变更
**原因**：GitHub Actions不允许使用以`GITHUB_`开头的自定义环境变量名

| 变更前 | 变更后 | 说明 |
|--------|--------|------|
| `GITHUB_TOKEN` | `GH_TOKEN` | GitHub Personal Access Token |

### 2. LLM API变量名统一
**原因**：支持多种LLM提供商，使用通用变量名更合理

| 变更前 | 变更后 | 说明 |
|--------|--------|------|
| `DEEPSEEK_API_KEY` | `LLM_API_KEY` | 统一的LLM API密钥 |
| `OPENAI_API_KEY` | `LLM_API_KEY` | 统一的LLM API密钥 |

### 3. 保持不变的变量
| 变量名 | 说明 |
|--------|------|
| `EMAIL_PASSWORD` | 邮箱应用专用密码 |

## 📝 当前完整的环境变量配置

### config/secrets.env
```env
# LLM API 密钥 (支持DeepSeek、OpenAI等)
LLM_API_KEY=your_llm_api_key_here

# GitHub Personal Access Token
GH_TOKEN=your_github_token_here

# 邮箱应用专用密码
EMAIL_PASSWORD=your_email_password_here
```

## 🚀 GitHub Secrets配置

在GitHub仓库设置中需要配置以下3个Secrets：

1. **LLM_API_KEY**
   - 值：你的LLM API密钥 (DeepSeek或OpenAI)
   - 格式：`sk-xxxxxxxxxxxxxxxx`

2. **GH_TOKEN**
   - 值：你的GitHub Personal Access Token
   - 格式：`ghp_xxxxxxxxxxxxxxxx`
   - 权限：`repo`, `workflow`

3. **EMAIL_PASSWORD**
   - 值：你的邮箱应用专用密码
   - 格式：根据邮箱提供商而定

## 🔍 影响的文件

### 配置文件
- ✅ `config/secrets.env`
- ✅ `config/secrets.env.example`

### 代码文件
- ✅ `src/github_uploader/github_client.py`
- ✅ `src/main.py`

### 工作流文件
- ✅ `.github/workflows/daily-paper-crawler.yml`

### 文档文件
- ✅ `README.md`
- ✅ `CONFIGURATION_GUIDE.md`
- ✅ `DEPLOYMENT_CHECKLIST.md`

## ⚠️ 迁移注意事项

### 如果你已经配置了旧的变量名：

1. **更新本地secrets.env文件**
   ```bash
   # 编辑 config/secrets.env
   # 将 GITHUB_TOKEN 改为 GH_TOKEN
   # 将 DEEPSEEK_API_KEY 改为 LLM_API_KEY
   ```

2. **更新GitHub Secrets**
   - 删除旧的 `DEEPSEEK_API_KEY` Secret
   - 删除旧的 `GITHUB_TOKEN` Secret (如果存在)
   - 添加新的 `LLM_API_KEY` Secret
   - 添加新的 `GH_TOKEN` Secret

3. **验证配置**
   ```bash
   # 运行测试确认配置正确
   python src/main.py --email-only
   ```

## ✅ 验证清单

配置完成后，请确认：

- [ ] `config/secrets.env` 使用新的变量名
- [ ] GitHub Secrets 配置了新的变量名
- [ ] 本地测试运行正常
- [ ] GitHub Actions 运行正常

## 🎯 优势

### 1. 符合GitHub规范
- 避免使用GitHub保留的环境变量前缀
- 确保GitHub Actions正常运行

### 2. 更好的通用性
- `LLM_API_KEY` 支持任何OpenAI兼容的API
- 便于切换不同的LLM提供商

### 3. 更简洁的配置
- 只需要3个环境变量
- 配置逻辑清晰明了

## 📞 获取帮助

如果在变量名变更过程中遇到问题：

1. 检查所有文件是否使用了新的变量名
2. 确认GitHub Secrets配置正确
3. 运行本地测试验证配置
4. 查看GitHub Actions运行日志

---

**变更完成日期**：2025-06-12
**影响版本**：v1.0.0+
