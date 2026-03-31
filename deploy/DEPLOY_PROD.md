# 生产部署说明（Linux / Ubuntu）

这套部署默认面向 `Ubuntu/Debian`，使用：

- `systemd` 管理进程
- `nginx` 做反向代理
- 项目目录默认 `/opt/gosuan`

## 1. 服务器上一键部署

先准备机器：

- 一台 Linux 服务器
- 可以访问 GitHub
- 使用 `root` 或 `sudo`

直接运行：

```bash
sudo APP_DIR=/opt/gosuan \
APP_NAME=gosuan \
APP_USER=root \
BRANCH=main \
DOMAIN=your-domain.com \
GOSUAN_AI_ENABLED=true \
GOSUAN_AI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3 \
GOSUAN_AI_MODEL=doubao-seed-2-0-code-preview-260215 \
GOSUAN_AI_API_KEY=你的Key \
bash deploy/linux_prod_setup.sh
```

如果暂时不需要 nginx，只想先把服务跑起来：

```bash
sudo ENABLE_NGINX=0 bash deploy/linux_prod_setup.sh
```

## 2. 从拉代码开始的完整命令

```bash
git clone https://github.com/xxlandlgh/gosuan.git
cd gosuan
chmod +x deploy/linux_prod_setup.sh
sudo APP_DIR=/opt/gosuan \
APP_NAME=gosuan \
APP_USER=root \
BRANCH=main \
DOMAIN=your-domain.com \
GOSUAN_AI_ENABLED=true \
GOSUAN_AI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3 \
GOSUAN_AI_MODEL=doubao-seed-2-0-code-preview-260215 \
GOSUAN_AI_API_KEY=你的Key \
bash deploy/linux_prod_setup.sh
```

## 3. 部署成功后的常用命令

查看服务状态：

```bash
systemctl status gosuan
```

查看日志：

```bash
journalctl -u gosuan -f
```

重启服务：

```bash
systemctl restart gosuan
```

测试接口：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1/health
```

## 4. 更新代码

如果后面你已经在服务器上部署过，只需要再次执行：

```bash
cd /opt/gosuan
git fetch origin
git reset --hard origin/main
sudo bash deploy/linux_prod_setup.sh
```

## 5. 这套脚本会做什么

脚本会自动完成：

- 安装 `git`、`python3`、`venv`、`nginx`
- 拉取或更新代码
- 创建虚拟环境
- 安装项目依赖
- 写入 `.env.local`
- 注册 `systemd` 服务
- 配置 `nginx`
- 启动服务并做健康检查

## 6. 重要说明

- `.env.local` 会写到服务器的项目目录下，权限设为 `600`
- 当前限流是应用内存级，服务重启后会重置
- 如需 HTTPS，建议部署完成后再配 `certbot` / `acme.sh`
