# 环境变量配置指南

## 📋 概述

LLM4ArxivPaper 使用环境变量来管理敏感信息（如 API 密钥、邮件密码等）。本文档说明了所有可用的环境变量及其用途。

---

## 🔑 环境变量列表

### 必需变量

以下变量在特定模式下是**必需的**，缺失会导致程序无法正常运行：

#### 1. `API_KEY`
- **用途**: OpenAI API 密钥
- **必需条件**: `runtime.mode = "online"` 时必需
- **获取方式**: 从 [OpenAI Platform](https://platform.openai.com/api-keys) 获取
- **示例**:
  ```bash
  export API_KEY="sk-proj-xxxxxxxxxxxxxxxxxxxxx"
  ```

#### 2. `MAIL_USERNAME`
- **用途**: SMTP 邮件发送用户名（通常是邮箱地址）
- **必需条件**: `email.enabled = true` 时必需
- **示例**:
  ```bash
  export MAIL_USERNAME="your-email@gmail.com"
  ```

#### 3. `MAIL_PASSWORD`
- **用途**: SMTP 邮件密码或应用专用密码
- **必需条件**: `email.enabled = true` 时必需
- **注意**: 建议使用应用专用密码，而非账户主密码
- **示例**:
  ```bash
  export MAIL_PASSWORD="your-app-specific-password"
  ```

---

### 可选变量

以下变量是**可选的**，未设置时会使用默认值：

#### 4. `BASE_URL`
- **用途**: OpenAI API 基础 URL
- **默认值**: `https://api.openai.com/v1`
- **使用场景**: 
  - 使用 Azure OpenAI 服务
  - 使用 OpenAI 兼容的第三方服务
- **示例**:
  ```bash
  # Azure OpenAI
  export BASE_URL="https://your-resource.openai.azure.com/"
  
  # 其他兼容服务
  export BASE_URL="https://api.your-provider.com/v1"
  ```

---

## 🚀 快速设置

### 方法 1: 临时设置（当前会话）

```bash
# 设置 OpenAI API Key（online 模式必需）
export API_KEY="sk-proj-xxxxxxxxxxxxxxxxxxxxx"

# 设置自定义 API 基础 URL（可选）
export BASE_URL="https://api.openai.com/v1"

# 设置邮件配置（如果需要邮件功能）
export MAIL_USERNAME="your-email@gmail.com"
export MAIL_PASSWORD="your-app-specific-password"

# 运行程序
python src/main.py
```

### 方法 2: 永久设置（推荐）

#### macOS / Linux (Zsh)
编辑 `~/.zshrc`:
```bash
nano ~/.zshrc
```

添加以下内容：
```bash
# LLM4ArxivPaper Environment Variables
export API_KEY="sk-proj-xxxxxxxxxxxxxxxxxxxxx"
export BASE_URL="https://api.openai.com/v1"  # 可选
export MAIL_USERNAME="your-email@gmail.com"
export MAIL_PASSWORD="your-app-password"
```

保存后重新加载配置：
```bash
source ~/.zshrc
```

#### macOS / Linux (Bash)
编辑 `~/.bashrc` 或 `~/.bash_profile`，步骤同上。

#### Windows (PowerShell)
```powershell
[Environment]::SetEnvironmentVariable("API_KEY", "sk-proj-xxxxxxxxxxxxxxxxxxxxx", "User")
[Environment]::SetEnvironmentVariable("MAIL_USERNAME", "your-email@gmail.com", "User")
[Environment]::SetEnvironmentVariable("MAIL_PASSWORD", "your-app-password", "User")
```

### 方法 3: 使用 `.env` 文件（开发环境）

创建 `.env` 文件（确保添加到 `.gitignore`）：
```bash
# .env
API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
BASE_URL=https://api.openai.com/v1
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

使用前加载：
```bash
# 使用 export 命令加载
set -a
source .env
set +a

# 或使用 python-dotenv（需要修改代码支持）
```

---

## ✅ 验证配置

运行配置验证脚本：
```bash
python tests/test_config_validation.py
```

输出示例：
```
======================================================================
Testing Configuration Validation
======================================================================

📋 Current Environment Variables:
   API_KEY: ✓ Set
   BASE_URL: ✓ Set (will use default)
   MAIL_USERNAME: ✗ Not set
   MAIL_PASSWORD: ✗ Not set

======================================================================
⚠️  Configuration Validation Warnings:
======================================================================

  Field: openai.base_url
  Issue: Environment variable ${BASE_URL} not set, using default: https://api.openai.com/v1

======================================================================

✅ Configuration loaded successfully!
```

---

## 🔍 配置验证规则

### Online 模式验证
当 `runtime.mode = "online"` 时：
- ✅ 必须设置 `API_KEY`
- ⚠️  未设置 `BASE_URL` 会使用默认值

### Email 功能验证
当 `email.enabled = true` 时：
- ✅ 必须设置 `MAIL_USERNAME`
- ✅ 必须设置 `MAIL_PASSWORD`
- ✅ 必须配置 `smtp_host`
- ⚠️  未设置收件人会发出警告

### Offline 模式
当 `runtime.mode = "offline"` 时：
- ℹ️  不需要设置 `API_KEY`
- ℹ️  使用启发式评分，不调用 API

---

## 🛡️ 安全最佳实践

### 1. 不要将敏感信息提交到版本控制
```bash
# 确保 .gitignore 包含：
.env
.env.local
*.secret
```

### 2. 使用应用专用密码
- Gmail: [应用专用密码设置](https://support.google.com/accounts/answer/185833)
- Outlook: [应用密码设置](https://support.microsoft.com/account-billing/manage-app-passwords-d6dc8c6d-4bf7-4851-ad95-6d07799387e9)

### 3. 定期轮换密钥
- 定期更新 API 密钥
- 如果密钥泄露，立即撤销并生成新密钥

### 4. 限制权限
- 为 API 密钥设置最小权限
- 使用只读或受限访问的邮件账户

---

## ❓ 常见问题

### Q: 为什么我的环境变量没有生效？
A: 
1. 确保在运行程序前设置了环境变量
2. 如果修改了 shell 配置文件，需要 `source ~/.zshrc` 重新加载
3. 检查变量名是否正确（区分大小写）

### Q: 如何查看当前设置的环境变量？
A:
```bash
# 查看单个变量
echo $API_KEY

# 查看所有相关变量
env | grep -E "API_KEY|BASE_URL|MAIL_"
```

### Q: 可以在配置文件中直接写入密钥吗？
A: **强烈不建议**！这样做会：
- 将敏感信息暴露在版本控制中
- 增加安全风险
- 难以在不同环境间切换

正确做法是使用环境变量或密钥管理服务。

### Q: 程序报错 "API_KEY is required in online mode"
A: 你需要设置 API_KEY：
```bash
export API_KEY="your-actual-api-key"
```
或者切换到 offline 模式：
```yaml
# config/pipeline.yaml
runtime:
  mode: "offline"  # 改为 offline
```

---

## 📚 相关资源

- [OpenAI API 文档](https://platform.openai.com/docs/)
- [Gmail SMTP 设置](https://support.google.com/mail/answer/7126229)
- [环境变量最佳实践](https://12factor.net/config)

---

**更新时间**: 2025-10-06  
**维护者**: LLM4ArxivPaper Team
