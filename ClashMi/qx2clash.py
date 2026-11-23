#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qx2clash.py —— Quantumult X 清单(.list/conf 片段) 转 Clash/mihomo 规则行

用途：clashmi-override.yaml 里的 Apple / Unbreak / Custom 三段规则是内联的，
上游清单更新后，重跑本脚本把它们原地刷进覆写文件。

用法：
  # 只看转换结果
  python qx2clash.py Apple.list
  python qx2clash.py https://cdn.jsdelivr.net/gh/tankui-cq/apple-policy@main/Apple.list

  # 原地刷新 clashmi-override.yaml 里对应的段落（按标记替换）
  python qx2clash.py Apple.list    --inject clashmi-override.yaml --marker APPLE
  python qx2clash.py Unbreak.list  --inject clashmi-override.yaml --marker UNBREAK
  python qx2clash.py Custom.list   --inject clashmi-override.yaml --marker CUSTOM

转换规则：
  HOST            -> DOMAIN
  HOST-SUFFIX     -> DOMAIN-SUFFIX
  HOST-KEYWORD    -> DOMAIN-KEYWORD
  HOST-WILDCARD   -> DOMAIN-REGEX（glob 转正则，整串锚定）
  IP-CIDR         -> IP-CIDR,...,no-resolve
  IP6-CIDR        -> IP-CIDR6,...,no-resolve
  USER-AGENT      -> 丢弃（mihomo 没有 UA 规则；QX 侧未开 MITM 时这些规则本来也不生效）
  第三列策略      -> 原样作为目标策略组；direct/proxy/reject 映射为 DIRECT/节点选择/REJECT
"""
import argparse
import re
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 内置策略映射（QX 小写 -> Clash）
POLICY_MAP = {
    "direct": "DIRECT",
    "proxy": "节点选择",
    "reject": "REJECT",
    "direct,no-resolve": "DIRECT",
}

IP_RULE_TYPES = {"IP-CIDR", "IP6-CIDR", "IP-CIDR6"}


def fetch(src: str) -> str:
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": "qx2clash/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8-sig", errors="replace")
    with open(src, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def glob_to_regex(pattern: str) -> str:
    out = []
    for ch in pattern:
        if ch == "*":
            out.append(".*")
        elif ch == "?":
            out.append(".")
        elif ch in r".+()[]{}|^$\\":
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "^" + "".join(out) + "$"


def convert(text: str):
    rules, stats = [], {"total": 0, "dropped_ua": 0, "no_policy": 0}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        parts = [p.strip() for p in line.split(",")]
        rtype = parts[0].upper()
        if rtype in ("PAYLOAD", "RULES"):
            continue
        stats["total"] += 1

        if rtype == "USER-AGENT":
            stats["dropped_ua"] += 1
            continue

        if rtype == "HOST":
            new_type = "DOMAIN"
        elif rtype in ("HOST-SUFFIX", "HOST-SUFFIX-REGEX"):
            new_type = "DOMAIN-SUFFIX"
        elif rtype == "HOST-KEYWORD":
            new_type = "DOMAIN-KEYWORD"
        elif rtype == "HOST-WILDCARD":
            new_type = "DOMAIN-REGEX"
        elif rtype in IP_RULE_TYPES:
            new_type = "IP-CIDR6" if "6" in rtype else "IP-CIDR"
        elif rtype in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-REGEX"):
            new_type = rtype
        else:
            print(f"# 跳过不支持的类型: {line}", file=sys.stderr)
            continue

        if len(parts) < 2:
            continue
        value = parts[1]
        policy = parts[-1] if len(parts) >= 3 else ""
        if len(parts) < 3 or not policy:
            policy = "DIRECT"
            stats["no_policy"] += 1
        policy = POLICY_MAP.get(policy.lower(), POLICY_MAP.get(policy, policy))

        if new_type == "DOMAIN-REGEX":
            value = glob_to_regex(value)

        if new_type in ("IP-CIDR", "IP-CIDR6"):
            rules.append(f"{new_type},{value},{policy},no-resolve")
        else:
            rules.append(f"{new_type},{value},{policy}")
    return rules, stats


def inject(patch_path: str, marker: str, rules):
    with open(patch_path, "r", encoding="utf-8") as f:
        content = f.read()
    begin = f"# >>> GENERATED:{marker}"
    end = f"# <<< GENERATED:{marker}"
    if begin not in content or end not in content:
        raise SystemExit(f"覆写文件里找不到标记 {begin} / {end}")
    head, rest = content.split(begin, 1)
    _, tail = rest.split(end, 1)
    body = "\n".join("  - '" + r.replace("'", "''") + "'" for r in rules)
    new = f"{head}{begin}\n{body}\n  {end}{tail}"
    with open(patch_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print(f"已写入 {patch_path} 的 {marker} 段：{len(rules)} 条规则")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="QX 清单本地路径或 URL")
    ap.add_argument("--inject", metavar="PATCH_YAML", help="把结果写回覆写文件")
    ap.add_argument("--marker", default="", help="覆写文件里的生成段标记名，如 APPLE")
    args = ap.parse_args()

    rules, stats = convert(fetch(args.source))
    if args.inject:
        if not args.marker:
            raise SystemExit("--inject 需要同时给 --marker")
        inject(args.inject, args.marker, rules)
    else:
        print("\n".join(rules))

    print(
        f"# 统计: 有效行 {stats['total']}，输出 {len(rules)}，"
        f"丢弃 USER-AGENT {stats['dropped_ua']}，无策略默认 DIRECT {stats['no_policy']}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
