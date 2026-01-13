# 利用clawcloud容器实现docker自动执行telegram bot特殊签到指令

## 准备工作：
1. 首先在 https://my.telegram.org/ 中获取api和hash，并将代码中的信息替换为你自己的 API和hash
2. 将以下代码在本地跑通，进行验证(输入手机号和验证码)，获取chat_name.session（自动生成在你的文件夹下），上传chat_name.session到github中。
3. 首次使用需要将代码打包下载下来后输入手机号和验证码（code）获取账号相关session值自动保存在本地文件夹，记得加上手机区号，如+86
4. 请将仓库设置为private，确保你的私有密钥不会公开
5. 给本项目点个Star，支持下本项目

```python
from telethon import TelegramClient, events
import asyncio

# 替换为你自己的 API 信息
api_id = 你的api_id
api_hash = '你的api_hash'
CHANNEL_ID = ' @你要发送的机器人用户名'

async def main():
    async with TelegramClient('chat_name', api_id, api_hash) as client:
        # 发送 '/checkin' 可以修改为你需要的指令
        await client.send_message(CHANNEL_ID, '/checkin')

        # 定义一个 future 用于等待消息
        future = asyncio.get_event_loop().create_future()

        @client.on(events.NewMessage(incoming=True, chats=CHANNEL_ID))
        async def handler(event):
            print("收到回复:", event.text)
            if not future.done():
                future.set_result(True)  # 收到消息后设置 future 完成

        # 等待 future 完成（即收到一条消息后退出）
        await future

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except SystemExit:
        print('finished')
```

然后将你生成的session拉入仓库中替换掉原有的session，然后执行以下步骤创建一个github action来制作容器的镜像文件，并根据以下步骤将其上传到clawcloud容器中

## 打包为可执行容器镜像流程概述

GitHub Actions → 构建 Docker 镜像 → 推送到 GHCR（GitHub 自己的容器仓库）→ clawcloud 拉取 GHCR 的私有镜像 → 部署运行。

## 一、前置准备（5 分钟搞定）

### 1. 确认文件清单（和之前一致，无需修改）
本地文件夹里保留 3 个文件（后续上传到 GitHub 私有仓库）：
- checkin.py
- Dockerfile
- chat_name.session

### 2. 创建 GitHub Personal Access Token (PAT)（用于 GHCR 登录）

GHCR 需要这个 Token 来授权 GitHub Actions 推送镜像，以及 clawcloud 拉取镜像：

1. 登录 GitHub → 点击右上角头像 → Settings → 左侧Developer settings → Personal access tokens → Tokens (classic) → Generate new token。
2. 配置 Token 权限（必须选这些，少一个都不行）：
   - Note：填个名字（比如ghcr-access）。
   - Expiration：选No expiration（长期使用）。
   - Scopes：
     - repo：全选（仓库权限）。
     - write:packages + read:packages + delete:packages（容器仓库权限）。
     - workflow（Actions 工作流权限）。
3. 点击Generate token → 复制 Token（只显示一次，务必保存好！）。

## 二、GitHub 全程操作

### 步骤 1：新建 GitHub 私有仓库
1. 登录 GitHub → 新建仓库 → 关键配置：
   - Repository name：telegram-checkin（自定义）。
   - Visibility：选Private（私有！避免 session 泄露）。
   - 点击Create repository。
2. 上传文件：仓库主页 → Add file → Upload files → 上传checkin.py、Dockerfile、chat_name.session → Commit changes。

### 步骤 2：配置 GitHub Secrets（存 PAT）
把刚才生成的 GitHub PAT 存到仓库的 Secrets 里，供 Actions 使用：
1. 仓库 → Settings → 左侧Secrets and variables → Actions → New repository secret。
2. 添加 1 个 Secret：
   - Name：GHCR_PAT（固定名字，后续 Actions 会用到）。
   - Secret：粘贴刚才复制的 GitHub PAT。

### 步骤 3：创建 GitHub Actions 工作流（推镜像到 GHCR）
1. 仓库 → Actions → set up a workflow yourself → 清空默认内容，粘贴下面的代码：

```yaml
name: 构建并推送镜像到GHCR（无Docker Hub）

# 触发条件：推代码到main分支时自动构建
on:
  push:
    branches: [ main ]

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      packages: write  # 授予推送镜像到GHCR的权限
      contents: read   # 授予读取仓库代码的权限

    steps:
      # 步骤1：拉取GitHub仓库里的代码（含py、Dockerfile、session）
      - name: 拉取仓库代码
        uses: actions/checkout@v4

      # 步骤2：登录GitHub容器仓库（GHCR）
      - name: 登录GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}  # 自动获取你的GitHub用户名
          password: ${{ secrets.GHCR_PAT }}  # 用之前存的PAT

      # 步骤3：构建并推送镜像到GHCR
      - name: 构建+推送镜像
        uses: docker/build-push-action@v5
        with:
          context: .  # 构建上下文（当前仓库根目录）
          push: true  # 推送到GHCR
          # 镜像地址格式：ghcr.io/你的GitHub用户名/镜像名:标签（必须小写！）
          tags: ghcr.io/${{ github.actor }}/telegram-checkin:latest
          # 镜像私有（继承仓库私有属性）
          labels: |
            org.opencontainers.image.source=https://github.com/${{ github.repository }}
```

3. 点击Commit new file → 等待 Actions 运行（仓库→Actions→ 看到绿色对勾 = 构建 + 推送成功）。

### 步骤 4：确认 GHCR 镜像已推送成功
GitHub 主页 → 点击顶部Your profile → 左侧Packages → 能看到telegram-checkin镜像（状态是 Private）→ 确认镜像存在。

## 三、clawcloud 部署（拉取 GHCR 的私有镜像）

现在 clawcloud 只需要拉取 GHCR 的镜像即可，全程无 Docker Hub，配置如下：

### 配置项填写内容（照抄替换即可）

| 配置项 | 填写内容 |
|--------|----------|
| Application Name | telegram-checkin-bot（随便填，识别用） |
| Image | Public/Private选Private（GHCR 镜像是私有） |
| Image Name | ghcr.io/你的GitHub用户名/telegram-checkin:latest（全小写！ 比如 ghcr.io/xiaoming/telegram-checkin:latest） |
| Image Username | 你的 GitHub 用户名（比如 xiaoming，全小写） |
| Image Password | 你之前生成的 GitHub PAT（就是存在 GHCR_PAT 里的那个） |
| Network | 保持默认 → 关闭Public Access（灰色，脚本不需要对外访问） |
| Image Registry | 改为 ghcr.io |

## 部署后验证

1. 点击 clawcloud 的「部署」→ 等待容器启动。
2. 查看容器日志：
   - 看到启动Telegram自动脚本 | checkin每日0:01 | upgrade每71小时 → 启动成功。
   - 首次运行会立即执行/checkin和/upgrade（upgrade 首次计时是 71 小时前）。
   - 后续每天北京时间 0:01 自动执行/checkin，每 71 小时执行一次/upgrade。
     <img width="1033" height="445" alt="image" src="https://github.com/user-attachments/assets/cb0c7236-b8b1-4849-8d66-7396e5102ce5" />


