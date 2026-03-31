# gosuan（个人玄学算卦/财运/择日/搬迁/动工）

> 说明：本项目用于**传统命理/择日的规则化计算**与**AI 辅助解读**。内容仅供文化娱乐与自我反思参考，不构成医疗/法律/投资建议。

## 功能概览

- **八字命盘**：四柱（年/月/日/时）、五行分布、十神、地支藏干（基于 `lunar-python`）。
- **财运解读**：基于十神（财星/官杀/印比食伤）与五行偏旺偏弱的结构性分析 + 可选 AI 生成“个性化文字报告”。
- **择日（搬迁/动工/开业等）**：
  - 过滤：冲生肖、月破/岁破（简化规则）、不利日（简化黑名单）
  - 评分：优先“建除十二神”里的吉神类别（若库可取到），再结合冲合与周末/工作日偏好
  - 输出：候选日期列表（含原因与禁忌提示）
- **AI 对接（可选）**：支持 OpenAI 官方或任何 **OpenAI 兼容协议**的模型（如阿里/智谱/DeepSeek/Qwen 的兼容网关、或你自建代理）。

## 环境要求

- Windows / macOS / Linux
- Python **3.10+**

## 安装

在项目根目录执行：

```bash
python -m pip install -U pip
pip install -e .
pip install -e ".[dev]"
```

## CLI 使用

说明：

- 现在 CLI 默认输出更适合直接阅读的中文结果。
- 如果你要把结果接到脚本、程序或二次处理流程里，可以为任意命令追加 `--json`。

### 1) 生成命盘与财运解读（不使用 AI）

```bash
gosuan bazi --name 张三 --gender male --birth "1995-08-17 14:30" --tz "Asia/Shanghai"
gosuan wealth --name 张三 --gender male --birth "1995-08-17 14:30" --tz "Asia/Shanghai"

# 如需原始 JSON
gosuan bazi --name 张三 --gender male --birth "1995-08-17 14:30" --tz "Asia/Shanghai" --json
```

### 2) 择日：给搬迁/动工挑日子

```bash
gosuan select-date --purpose move --name 张三 --gender male --birth "1995-08-17 14:30" --tz "Asia/Shanghai" --start 2026-04-01 --end 2026-05-31 --limit 10
gosuan select-date --purpose construction --name 张三 --gender male --birth "1995-08-17 14:30" --tz "Asia/Shanghai" --start 2026-04-01 --end 2026-05-31 --limit 10

# 只找这段时间里“最合适的 1 天”
gosuan select-date --purpose move --name 张三 --gender male --birth "1995-08-17 14:30" --tz "Asia/Shanghai" --start 2026-04-01 --end 2026-05-31 --best

# 必须命中黄历“宜”的目的关键词，否则剔除（更严格）
gosuan select-date --purpose move --name 张三 --gender male --birth "1995-08-17 14:30" --tz "Asia/Shanghai" --start 2026-04-01 --end 2026-05-31 --must-hit-yi --best

# 排除指定日期（可重复传）
gosuan select-date --purpose move --name 张三 --gender male --birth "1995-08-17 14:30" --tz "Asia/Shanghai" --start 2026-04-01 --end 2026-05-31 --exclude-date 2026-04-05 --exclude-date 2026-04-12

# 选择“最匹配”的择日流派（默认 best_fit）
gosuan select-date --school best_fit --purpose move --name 张三 --gender male --birth "1995-08-17 14:30" --tz "Asia/Shanghai" --start 2026-04-01 --end 2026-05-31 --best

# 更严格（strict）：必须命中“宜”，且建除十二神落在强吉类
gosuan select-date --school strict --purpose move --name 张三 --gender male --birth "1995-08-17 14:30" --tz "Asia/Shanghai" --start 2026-04-01 --end 2026-05-31 --best
```

### 3) 算卦（梅花易数起卦）

```bash
# 以问事时间起卦（偏“通用”）
gosuan divine --name 张三 --gender male --birth "1995-08-17 14:30" --tz "Asia/Shanghai" --question-time "2026-04-01 09:30"

# 更贴合个人：把出生信息作为种子（建议开启）
gosuan divine --with-person --name 张三 --gender male --birth "1995-08-17 14:30" --tz "Asia/Shanghai" --question-time "2026-04-01 09:30"
```

### 3) 开启 AI 解读（可选）

设置环境变量：

- `GOSUAN_AI_BASE_URL`：兼容网关地址
- `GOSUAN_AI_API_KEY`：API Key
- `GOSUAN_AI_MODEL`：模型名

推荐先用一个零门槛的免费兼容方案：

```bash
# 推荐默认值
set GOSUAN_AI_BASE_URL=https://openrouter.ai/api/v1
set GOSUAN_AI_MODEL=openrouter/free
set GOSUAN_AI_API_KEY=你的_OpenRouter_Key
```

如果你想直接本地保存配置，也可以在项目根目录新建 `.env.local`，项目会自动读取。

当前项目已经支持这种本地方式，且 `.env.local` 已被 [`.gitignore`](D:/gitProject/gosuan/.gitignore) 忽略，适合放你自己的 key。

豆包大模型示例：

```bash
GOSUAN_AI_ENABLED=true
GOSUAN_AI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
GOSUAN_AI_MODEL=doubao-1-5-pro-32k-250115
GOSUAN_AI_API_KEY=你的豆包Key
```

然后：

```bash
gosuan wealth --name 张三 --gender male --birth "1995-08-17 14:30" --tz "Asia/Shanghai" --ai
```

## HTTP API

启动：

```bash
gosuan-api
```

默认监听 `http://127.0.0.1:8000`，文档在 `http://127.0.0.1:8000/docs`。

如果你希望 API 直接返回更适合阅读的中文结果，可以追加 `pretty_cn=true`：

```bash
POST /bazi?pretty_cn=true
POST /daily-fortune?pretty_cn=true
POST /divine?pretty_cn=true
POST /select-date?pretty_cn=true
POST /wealth?pretty_cn=true&ai=true
```

还可以访问：

```bash
GET /ai-status
```

用来查看当前服务是否已经读到 AI 配置，以及当前模型名。

## 生产部署

仓库内已提供 Linux 生产部署脚本：

- [deploy/linux_prod_setup.sh](D:/gitProject/gosuan/deploy/linux_prod_setup.sh)
- [deploy/DEPLOY_PROD.md](D:/gitProject/gosuan/deploy/DEPLOY_PROD.md)

典型部署方式：

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

脚本会自动完成：

- 安装系统依赖
- 拉代码 / 更新代码
- 创建虚拟环境
- 安装 Python 依赖
- 写入 `.env.local`
- 注册 `systemd`
- 配置 `nginx`
- 启动并健康检查

## 测试

```bash
python -m pytest -q
```

## 重要提示（边界与局限）

- **命理算法**在不同流派差异极大：本项目优先做到“可复核的规则计算 + 可扩展架构”，并提供清晰的解释字段，便于你后续把自己的师承规则补进去。
- **择日**模块目前采用“通行规则的可实现子集 + 可解释评分”。如你有固定流派（如玄空/三合/奇门/六壬/梅花等），我可以把对应规则做成插件式引擎。

