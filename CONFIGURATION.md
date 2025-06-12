# 参数配置指南

## LLM配置指南

本项目使用DeepSeek或OpenAI的API进行论文摘要生成，需要配置以下信息：

- **LLM_API_KEY**
  - 说明：API密钥，用于调用AI模型。
  - 获取方法：
    - [DeepSeek API 密钥获取](https://platform.deepseek.com/)
    - [OpenAI API 密钥获取](https://platform.openai.com/api-keys)

- **base_url**
  - 说明：LLM API的基础URL。
  - 示例：
    - DeepSeek: `https://api.deepseek.com`
    - OpenAI: `https://api.openai.com/v1`


## GitHub配置指南

为实现自动推送论文摘要到GitHub供给RTD生成文档，你需要进行如下配置：

### 仓库配置

1. 创建或使用已有的GitHub仓库。
2. 确认仓库名格式为 `用户名/仓库名`（RTD的仓库路径）。

### GitHub Token（GH_TOKEN）

- 作用：使脚本能自动推送文件到GitHub。
- 获取方法：
  - 登录GitHub → Settings → Developer settings → Personal access tokens
  - 创建新Token，选择权限 `repo` 和 `workflow`（保证最小权限）。
  - 复制生成的Token并保存到项目的`config/secrets.env`文件和仓库Secrets中，变量名为`GH_TOKEN`。

## 邮件服务配置指南

项目使用SMTP服务自动发送邮件报告，推荐使用Gmail进行设置：

### SMTP配置

- 服务：Gmail SMTP
- SMTP服务器: `smtp.gmail.com`
- 端口: `587`

### 应用专用密码（EMAIL_PASSWORD）

- 作用：用于安全地发送邮件，而不是使用邮箱登录密码。
- 获取方法：
  - 开启Google账户的[两步验证](https://myaccount.google.com/security)。
  - 在安全设置中生成“应用专用密码”。
  - 将此密码保存到项目的`config/secrets.env`文件和仓库Secrets中，变量名为`EMAIL_PASSWORD`。

### 收件邮箱

- 修改`config/config.yaml`中的`recipient_email`为你希望接收邮件的邮箱地址。
