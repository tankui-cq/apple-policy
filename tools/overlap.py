#!/usr/bin/env python3
"""统计两份清单与 Global.list 的同键重复（type,value 完全相同），供 QuanX 文档引用。"""
import urllib.request

URLS = {
    "Spotify": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/QuantumultX/Spotify/Spotify.list",
    "Twitter": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/QuantumultX/Twitter/Twitter.list",
    "Global": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/QuantumultX/Global/Global.list",
}


def parse(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        text = r.read().decode("utf-8")
    out = set()
    for line in text.splitlines():
        s = line.strip()
        if not s or s[0] in "#;":
            continue
        parts = [p.strip() for p in s.split(",")]
        if len(parts) >= 2:
            out.add((parts[0].upper(), parts[1].lower()))
    return out


data = {k: parse(v) for k, v in URLS.items()}
g = data["Global"]
for name in ("Spotify", "Twitter"):
    dup = sorted(data[name] & g)
    print(f"{name}: total={len(data[name])}  same-key with Global={len(dup)}")
    for t, v in dup[:40]:
        print(f"  {t},{v}")
