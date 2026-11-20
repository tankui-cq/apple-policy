#!/usr/bin/env python3
"""生成一份 Apple 分流清单（Quantumult X 格式，自带策略列）。

为什么是「一份」而不是「两份」：
    上游 Apple.list 有一条 HOST-SUFFIX,apple.com，它覆盖了 Apple-AI.list
    里的所有 *.apple.com 域名。分成两份清单时，谁先命中谁生效——而 QX 对
    远程清单的顺序并不可靠，实测把苹果服务排在前面就会把 gspe1-ssl.ls.apple.com
    送去直连（GCC 返回 CN）。
    合成一份之后，规则在文件内的先后顺序是确定的。

三段，顺序即优先级：
    1. Apple 智能（🍎 Apple 智能，走美国）——必须走美国，否则 Siri 里没有 ChatGPT
    2. 大流量（DIRECT）——App/系统更新/音乐/iCloud 备份，走国内 CDN
    3. Apple 服务（🍎 苹果服务，走美国）——兜底，其余都跟代理走

用法：
    python tools/build.py                            # 从上游拉最新
    python tools/build.py --apple a.txt --ai b.txt   # 用本地文件（离线）
"""

import argparse
import io
import sys
import urllib.request

APPLE_LIST_URL = (
    "https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master"
    "/rule/QuantumultX/Apple/Apple.list"
)
AI_LIST_URL = "https://cdn.jsdelivr.net/gh/RocM301/Apple-Rule@main/Apple-AI.list"

AI_POLICY = "🍎 Apple 智能"
SVC_POLICY = "🍎 苹果服务"
DIRECT_POLICY = "DIRECT"

# 大流量 Apple 域名：直连，交给国内 CDN 和运营商缓存。
# 依据 felixonmars/dnsmasq-china-list 的 apple.china.conf（165 条在中国有 CDN
# 节点的 Apple 域名），只取其中流量最大的几类：App 与内容下载、系统更新、
# 开发者下载、Apple Music 流媒体、iCloud 云盘/备份、地图瓦片。
# 其余（含推送、天气、账户、商店 API）照旧走美国，流量小，不值得单独维护。
# 注意：这份名单不能含任何 Apple 智能链路域名。guzzoni / seed / probe /
# gspe* 在 china.conf 里也有国内节点，但它们必须走美国。
CHINA_TRAFFIC = [
    # App Store 内容与图标（下载 App、封面、预览图）
    ("HOST-SUFFIX", "mzstatic.com"),
    ("HOST-SUFFIX", "iosapps.itunes.apple.com"),
    ("HOST-SUFFIX", "osxapps.itunes.apple.com"),
    ("HOST-SUFFIX", "iosapps.itunes.g.aaplimg.com"),
    ("HOST-SUFFIX", "osxapps.itunes.g.aaplimg.com"),
    ("HOST-SUFFIX", "cds.apple.com"),
    ("HOST-SUFFIX", "cds-cdn.v.aaplimg.com"),
    ("HOST-SUFFIX", "bag-cdn.itunes-apple.com.akadns.net"),
    # 系统更新（iOS / macOS / watchOS，单次几百 MB 到几 GB）
    ("HOST-SUFFIX", "appldnld.apple.com"),
    ("HOST-SUFFIX", "appldnld.g.aaplimg.com"),
    ("HOST-SUFFIX", "updates.cdn-apple.com"),
    ("HOST-SUFFIX", "updates-http.cdn-apple.com"),
    ("HOST-SUFFIX", "mesu.apple.com"),
    ("HOST-SUFFIX", "mesu-cdn.apple.com.akadns.net"),
    ("HOST-SUFFIX", "oscdn.apple.com"),
    ("HOST-SUFFIX", "swcdn.apple.com"),
    ("HOST-SUFFIX", "swcdn.g.aaplimg.com"),
    ("HOST-SUFFIX", "swdist.apple.com"),
    ("HOST-SUFFIX", "swscan.apple.com"),
    ("HOST-SUFFIX", "swcatalog.apple.com"),
    # 开发者下载（Xcode、模拟器、WWDC 视频）
    ("HOST-SUFFIX", "adcdownload.apple.com"),
    ("HOST-SUFFIX", "devimages-cdn.apple.com"),
    ("HOST-SUFFIX", "devstreaming-cdn.apple.com"),
    ("HOST-SUFFIX", "download.developer.apple.com"),
    # Apple Music 流媒体
    ("HOST-SUFFIX", "audio-ssl.itunes.apple.com"),
    ("HOST-SUFFIX", "audio.itunes.apple.com"),
    ("HOST-SUFFIX", "aod.itunes.apple.com"),
    # iCloud 云盘 / 照片 / 备份（真正的大头）
    ("HOST-SUFFIX", "icloud-content.com"),
    # 地图瓦片
    ("HOST-SUFFIX", "apple-mapkit.com"),
]

# 上游两份清单都没有、但属于 Apple 智能链路的域名。
# 前 4 条来自 QuanX-v1.conf 的本地规则：改用远程单文件后，上游 Apple-AI.list
# 没有覆盖它们，会掉进后面的 HOST-SUFFIX,apple.com / icloud.com 走直连。
# 中间 6 条用来替代上游的 HOST-KEYWORD,siri：关键字规则遇到更具体的
# HOST-SUFFIX,apple.com 时，在 QX 的「分流匹配优化」下可能被后者压掉，
# 结果 Siri 后端全部直连。改用精确域名后，任何匹配模式都稳。
# 最后 3 条是地区判定（决定 GCC 返回 US/CN 的开关）。上游把它们放在服务段，
# 靠「🍎 苹果服务」默认美国才生效——服务组一旦被手动切成 DIRECT，地区判定
# 立刻掉回 CN、Siri 里的 ChatGPT 消失，而且从「🍎 Apple 智能」组完全看不出来。
# 挪进 AI 段后与服务组的选态解耦，应急切 DIRECT 也不影响 AI。
EXTRA_AI = [
    ("HOST-SUFFIX", "apple-relay.akamaized.net"),
    ("HOST-SUFFIX", "apple-cloudkit.com"),
    ("HOST-SUFFIX", "p150-acsegateway.icloud.com"),
    ("HOST-SUFFIX", "gs-loc-cn.apple.com"),
    ("HOST", "guzzoni-apple-com.v.aaplimg.com"),
    ("HOST", "api-siri-prod.apple.com"),
    ("HOST", "seed.siri.apple.com"),
    ("HOST", "probe.siri.apple.com"),
    ("HOST", "seed-sequoia.siri.apple.com"),
    ("HOST", "seed-swallow.siri.apple.com"),
    ("HOST-SUFFIX", "siri.apple.com"),
    ("HOST-SUFFIX", "gs-loc.apple.com"),
    ("HOST-SUFFIX", "configuration.apple.com"),
    ("HOST", "bag.itunes.apple.com"),
]

# 上游 AI 清单里不可靠的规则：关键字匹配太宽，且优先级不稳定
DROP_AI = {
    ("HOST-KEYWORD", "siri"),
}

# 上游 Apple-AI.list 用 Clash 语法，这里统一转成 Quantumult X 的写法
TYPE_MAP = {
    "DOMAIN": "HOST",
    "DOMAIN-SUFFIX": "HOST-SUFFIX",
    "DOMAIN-KEYWORD": "HOST-KEYWORD",
    "DOMAIN-WILDCARD": "HOST-WILDCARD",
}


def fetch(url, fallback=None):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.read().decode("utf-8")
    except Exception as e:  # noqa: BLE001
        if fallback:
            print(f"  ! 拉取失败（{e}），改用本地文件 {fallback}", file=sys.stderr)
            return io.open(fallback, encoding="utf-8").read()
        raise


def parse(text):
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(";"):
            continue
        parts = [p.strip() for p in s.split(",")]
        if len(parts) < 2:
            continue
        t = parts[0].upper()
        out.append((TYPE_MAP.get(t, t), parts[1]))
    return out


def suffix_set(rules):
    return {v.lower() for t, v in rules if t == "HOST-SUFFIX"}


def covered(value, suffixes):
    """规则值是否已被某个 HOST-SUFFIX 覆盖（相等或子域）。"""
    v = value.lower()
    return any(v == s or v.endswith("." + s) for s in suffixes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apple", help="Apple.list 本地副本")
    ap.add_argument("--ai", help="Apple-AI.list 本地副本")
    args = ap.parse_args()

    print("拉取上游清单 ...", file=sys.stderr)
    apple_rules = parse(fetch(APPLE_LIST_URL, args.apple))
    ai_rules = parse(fetch(AI_LIST_URL, args.ai))

    ai = sorted(
        {(t, v) for t, v in ai_rules if (t, v) not in DROP_AI} | set(EXTRA_AI),
        key=lambda x: (x[0], x[1]),
    )
    direct = sorted(set(CHINA_TRAFFIC), key=lambda x: (x[0], x[1]))

    # 服务段只保留既不在 AI 段、也不被 AI/直连的 HOST-SUFFIX 覆盖的规则。
    # 像 HOST-SUFFIX,apple.com 这种覆盖型规则必须保留，靠文件内顺序让前面先命中。
    taken = set(ai) | set(direct)
    covered_by = suffix_set(ai) | suffix_set(direct)
    skip_types = {"HOST", "HOST-SUFFIX", "HOST-WILDCARD"}
    seen, service = set(), []
    for item in apple_rules:
        if item in taken or item in seen:
            continue
        if item[0] in skip_types and covered(item[1], covered_by):
            continue
        seen.add(item)
        service.append(item)

    header = (
        "# Apple 分流清单（Quantumult X）\n"
        "# 顺序即优先级：Apple 智能 -> 大流量直连 -> Apple 服务。\n"
        "# 生成：tools/build.py（勿手改）\n"
        "# AI 来源：https://github.com/RocM301/Apple-Rule -> Apple-AI.list\n"
        "# 服务来源：https://github.com/blackmatrix7/ios_rule_script -> Apple.list\n"
    )
    body = [f"{t},{v},{AI_POLICY}" for t, v in ai]
    body += [f"{t},{v},{DIRECT_POLICY}" for t, v in direct]
    body += [f"{t},{v},{SVC_POLICY}" for t, v in service]
    io.open("Apple.list", "w", encoding="utf-8", newline="\n").write(
        header + "\n".join(body) + "\n"
    )

    print(
        f"Apple.list  {len(body)} 条"
        f"（AI {len(ai)} + 直连 {len(direct)} + 服务 {len(service)}）"
    )


if __name__ == "__main__":
    main()
