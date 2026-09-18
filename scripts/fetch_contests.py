#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
contest-tracker 采集器
抓取 Kaggle / Codeforces / ICPC(ACM) / NOI(CSP) / 黑客松 比赛信息，归一化输出 contests.json

数据源策略（尽力而为，单源失败不影响其他源）：
  1. Codeforces  : 官方公开 API https://codeforces.com/api/contest.list  (无需凭据)
  2. Kaggle      : 可选凭据 KAGGLE_USERNAME/KAGGLE_KEY（GitHub Secrets）配置后自动启用；
                   未配置时尝试匿名抓取官网活动页
  3. ICPC (ACM)  : icpc.pku.edu.cn 新闻公告页（静态 HTML）
  4. NOI (CSP)   : noi.cn 首页新闻列表（静态 HTML）
  5. 黑客松      : hackathon.com 公开页 + 手动维护的 extra_hackathons.json

输出: docs/contests.json  (供 GitHub Pages 前端读取)
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

import urllib.request
import urllib.error

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 contest-tracker/1.0"
}
TIMEOUT = 25
CN_TZ = timezone(timedelta(hours=8))  # 中国时区显示


def http_get(url, timeout=TIMEOUT, headers=None):
    """通用 GET，返回文本；失败抛异常由调用方兜底。"""
    h = dict(UA)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    # 优先按响应头编码，否则 utf-8
    charset = r.headers.get_content_charset() or "utf-8"
    return data.decode(charset, errors="replace")


def to_iso(ts):
    """Unix 秒 -> ISO8601 (Asia/Shanghai)"""
    if not ts:
        return None
    return datetime.fromtimestamp(ts, CN_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")


def now_ts():
    return int(time.time())


# ---------------------------------------------------------------------------
# 1. Codeforces
# ---------------------------------------------------------------------------
def fetch_codeforces():
    url = "https://codeforces.com/api/contest.list?gym=false"
    raw = http_get(url)
    d = json.loads(raw)
    if d.get("status") != "OK":
        return []
    out = []
    for c in d.get("result", []):
        phase = c.get("phase", "")
        start = c.get("startTimeSeconds")
        dur = c.get("durationSeconds", 0)
        out.append({
            "platform": "codeforces",
            "platform_zh": "Codeforces",
            "name": c.get("name", ""),
            "url": f"https://codeforces.com/contest/{c.get('id')}",
            "start_time": to_iso(start),
            "end_time": to_iso(start + dur if start else None),
            "status": {
                "BEFORE": "upcoming", "CODING": "running",
                "PENDING_SYSTEM_TEST": "running", "SYSTEM_TEST": "running",
                "FINISHED": "finished"
            }.get(phase, "unknown"),
            "duration_sec": dur,
            "register_url": f"https://codeforces.com/contestRegistration/{c.get('id')}",
            "source": "codeforces-api",
        })
    return out


# ---------------------------------------------------------------------------
# 2. Kaggle（可选凭据）
# ---------------------------------------------------------------------------
def fetch_kaggle():
    user = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    out = []
    if user and key:
        # 官方 kaggle API v1
        try:
            url = "https://www.kaggle.com/api/v1/competitions/list"
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {key}",
                "X-Kaggle-Username": user,
                "User-Agent": UA["User-Agent"],
            })
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = json.loads(r.read().decode())
            for c in data:
                out.append({
                    "platform": "kaggle",
                    "platform_zh": "Kaggle",
                    "name": c.get("title", c.get("ref", "")),
                    "url": f"https://www.kaggle.com/competitions/{c.get('ref','')}",
                    "start_time": c.get("enabledDate") or None,
                    "end_time": c.get("deadline") or None,
                    "status": "upcoming" if c.get("deadline") and _is_future(c.get("deadline")) else "unknown",
                    "duration_sec": None,
                    "register_url": f"https://www.kaggle.com/competitions/{c.get('ref','')}",
                    "source": "kaggle-api",
                })
            return out
        except Exception as e:
            print(f"[warn] Kaggle API 失败: {e}", file=sys.stderr)
    # 未配置凭据：尝试匿名抓取活动页（拿不到则跳过）
    try:
        html = http_get("https://www.kaggle.com/competitions")
        # Kaggle 是 SPA，页面内可能无直接数据；这里仅占位记录
        if len(html) < 1000:
            print("[info] Kaggle 无凭据且页面为空壳，跳过（配置 KAGGLE_USERNAME/KEY 可启用）", file=sys.stderr)
    except Exception as e:
        print(f"[warn] Kaggle 匿名抓取失败: {e}", file=sys.stderr)
    return out


def _is_future(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.timestamp() > now_ts()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 3. ICPC / ACM（icpc.pku.edu.cn 新闻）
# ---------------------------------------------------------------------------
def fetch_icpc():
    out = []
    try:
        html = http_get("https://icpc.pku.edu.cn/index.htm")
        # 标题在内文文本，链接为相对路径
        for m in re.finditer(r'<a[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<inner>.*?)</a>', html, re.S):
            title = re.sub(r"<[^>]+>", "", m.group("inner")).strip()
            href = m.group("href")
            if not any(k in title for k in ("ICPC", "区域赛", "网络预选", "World Finals", "总决赛", "Asia")):
                continue
            if not href.startswith("http"):
                href = "https://icpc.pku.edu.cn/" + href.lstrip("/")
            # 日期：优先取链接附近日期，取不到则空
            dm = re.search(r"(\d{4}-\d{2}-\d{2})", m.group("inner"))
            date_str = dm.group(1) if dm else None
            out.append({
                "platform": "icpc",
                "platform_zh": "ICPC/ACM",
                "name": title.strip(),
                "url": href,
                "start_time": date_str,
                "end_time": None,
                "status": "announcement",
                "duration_sec": None,
                "register_url": href,
                "source": "icpc-pku",
            })
    except Exception as e:
        print(f"[warn] ICPC 抓取失败: {e}", file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# 4. NOI / CSP（noi.cn 首页新闻）
# ---------------------------------------------------------------------------
def fetch_noi():
    out = []
    try:
        html = http_get("https://www.noi.cn/")
        keys = ("NOI", "CSP", "NOIP", "IOI", "APIO", "省选", "冬令营", "精英培训", "女生竞赛")
        for m in re.finditer(r'<a[^>]*href="(?P<href>[^"]+)"[^>]*title="(?P<title>[^"]{4,100})"', html):
            title = m.group("title")
            href = m.group("href")
            if not any(k in title for k in keys):
                continue
            if not href.startswith("http"):
                href = "https://www.noi.cn" + href.lstrip("/")
            # 提取日期：/xw/2026-09-09/xxx.shtml
            dm = re.search(r"/(\d{4})-(\d{2})-(\d{2})/", href)
            date_str = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}" if dm else None
            out.append({
                "platform": "noi",
                "platform_zh": "NOI/CSP",
                "name": title.strip().replace("&#32;", " "),
                "url": href,
                "start_time": date_str,
                "end_time": None,
                "status": "announcement",
                "duration_sec": None,
                "register_url": href,
                "source": "noi-cn",
            })
    except Exception as e:
        print(f"[warn] NOI 抓取失败: {e}", file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# 5. 黑客松（hackathon.com + 手动维护）
# ---------------------------------------------------------------------------
def fetch_hackathons():
    out = []
    # 5a. 手动维护源（可选）
    extra_path = os.path.join(os.path.dirname(__file__), "..", "extra_hackathons.json")
    try:
        with open(extra_path, encoding="utf-8") as f:
            extra = json.load(f)
        for e in extra:
            out.append({
                "platform": "hackathon",
                "platform_zh": "黑客松",
                "name": e.get("name", ""),
                "url": e.get("url", ""),
                "start_time": e.get("start_time"),
                "end_time": e.get("end_time"),
                "status": e.get("status", "announcement"),
                "duration_sec": None,
                "register_url": e.get("url", ""),
                "source": "manual",
            })
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[warn] extra_hackathons.json 读取失败: {e}", file=sys.stderr)

    # 5b. hackathon.com 公开页（尽力而为）
    try:
        html = http_get("https://www.hackathon.com/")
        # 提取卡片：title + 日期 + 链接
        # 该站是聚合首页，正文多为 JS 渲染，能抓到的有限；不阻塞
        for m in re.finditer(r'href="(https://[^"]*hackathon[^"]*)"[^>]*>\s*<[^>]*>\s*([^<]{3,80})', html):
            out.append({
                "platform": "hackathon",
                "platform_zh": "黑客松",
                "name": m.group(2).strip(),
                "url": m.group(1),
                "start_time": None, "end_time": None,
                "status": "announcement",
                "duration_sec": None,
                "register_url": m.group(1),
                "source": "hackathon-com",
            })
    except Exception as e:
        print(f"[warn] hackathon.com 抓取失败: {e}", file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs = os.path.join(root, "docs")
    os.makedirs(docs, exist_ok=True)

    all_contests = []
    fetchers = [
        ("Codeforces", fetch_codeforces),
        ("Kaggle", fetch_kaggle),
        ("ICPC", fetch_icpc),
        ("NOI", fetch_noi),
        ("黑客松", fetch_hackathons),
    ]
    for name, fn in fetchers:
        try:
            items = fn()
            print(f"[OK] {name}: {len(items)} 条")
            all_contests.extend(items)
        except Exception as e:
            print(f"[FAIL] {name}: {e}", file=sys.stderr)

    # 去重（按 platform+name+url）
    seen = set()
    dedup = []
    for c in all_contests:
        k = (c["platform"], c["name"], c["url"])
        if k in seen:
            continue
        seen.add(k)
        dedup.append(c)

    # 窗口过滤：只保留"未来 180 天 + 过去 90 天"内的比赛（覆盖 1/3/6 个月需求）
    now = now_ts()
    future_win = now + 180 * 86400
    past_win = now - 90 * 86400
    kept = []
    for c in dedup:
        ts = None
        if c.get("start_time"):
            try:
                ts = datetime.fromisoformat(c["start_time"].replace("Z", "+00:00")).timestamp()
            except Exception:
                pass
        if ts is None:
            # 无时间信息的公告类（ICPC/NOI/黑客松）保留最近 30 条
            kept.append(c)
            continue
        if past_win <= ts <= future_win:
            kept.append(c)
    # 公告类（无时间）统一放最后，避免占据前排
    kept.sort(key=lambda c: (c.get("start_time") is None, c.get("start_time") or ""))

    payload = {
        "generated_at": datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S%z"),
        "total": len(kept),
        "contests": kept,
    }
    out_path = os.path.join(docs, "contests.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[DONE] 窗口过滤后 {len(kept)} 条 -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
