# 📡 比赛雷达 Contest Radar

> 一站式实时比赛信息跟踪：**Kaggle · Codeforces · ICPC/ACM · NOI/CSP · 黑客松**
> 每 6 小时自动采集更新，GitHub Pages 在线展示，支持近 1 / 3 / 6 个月筛选。

在线地址：**[https://cyberspace-cs.github.io/contest-tracker/](https://cyberspace-cs.github.io/contest-tracker/)**

---

## ✨ 功能

- 🕐 **实时跟踪**：GitHub Actions 每 6 小时自动抓取 5 大平台的比赛/活动信息
- 📅 **时间筛选**：近 1 个月 / 3 个月 / 6 个月一键切换
- 🔍 **搜索与筛选**：按平台过滤、按关键词搜索
- ⏳ **倒计时**：每场比赛显示「X 天后开始 / 今天开始 / 已结束 X 天」
- 🏷 **状态标识**：即将开始 / 进行中 / 公告报名 / 已结束
- 🔗 **一键跳转**：比赛主页、报名链接直达

## 🗂 数据源

| 平台 | 来源 | 凭据要求 |
| --- | --- | --- |
| Codeforces | 官方公开 API `codeforces.com/api/contest.list` | 无 |
| Kaggle | 官方 Kaggle API v1 | 可选（推荐配置，见下） |
| ICPC / ACM | `icpc.pku.edu.cn` 公告页 | 无 |
| NOI / CSP | `noi.cn` 首页新闻 | 无 |
| 黑客松 | `hackathon.com` + 手动维护 `extra_hackathons.json` | 无 |
| **国内AI赛事** | 手动维护 `extra_hackathons.json`（腾讯 WorkBuddy / TRAE / 德邻杯 / 北大 / 小红书 / 华为等） | 无 |

## 🚀 快速开始

### 在线查看（无需任何配置）

访问 GitHub Pages：`https://cyberspace-cs.github.io/contest-tracker/`

### 本地运行采集

```bash
pip install -r requirements.txt  # 可选，脚本仅用标准库
python3 scripts/fetch_contests.py
# 输出 docs/contests.json，浏览器打开 docs/index.html 即可预览
```

### 可选：启用 Kaggle 数据（推荐）

Kaggle 官方 API 需要账号凭据。在仓库 **Settings → Secrets and variables → Actions** 添加：

| Secret | 值 |
| --- | --- |
| `KAGGLE_USERNAME` | 你的 Kaggle 用户名 |
| `KAGGLE_KEY` | Kaggle API Key（在 Kaggle → Settings → API 创建） |

配置后下一次自动采集即会包含 Kaggle 比赛。

### 可选：手动维护黑客松

编辑 `extra_hackathons.json`，格式：

```json
[
  {
    "name": "比赛名称",
    "url": "https://...",
    "start_time": "2026-10-01T09:00:00+08:00",
    "end_time": "2026-10-02T18:00:00+08:00",
    "status": "announcement"
  }
]
```

## 🏗 架构

```text
contest-tracker/
├── .github/workflows/pages.yml   # 每 6h 定时采集 + 部署 Pages
├── scripts/
│   └── fetch_contests.py         # 多源采集器（归一化 + 容错 + 窗口过滤）
├── docs/
│   ├── index.html                # 展示页（时间轴 + 筛选 + 搜索）
│   └── contests.json             # 采集产物（自动生成，勿手改）
├── extra_hackathons.json         # 手动维护的黑客松源
└── README.md
```

## 🛠 自部署到自己的 GitHub

1. Fork 本仓库（或复制到自己的仓库）
2. 在 **Settings → Pages** 选择「GitHub Actions」作为构建来源
3. 推送 main 分支即自动触发首次采集 + 部署
4. 可选：添加 Kaggle Secrets（见上）

## 📜 License

MIT

---

*Made by buleboy · 数据仅供学习参考，比赛信息以各平台官网为准*
