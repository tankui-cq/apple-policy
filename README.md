# Quantumult X 规则列表

本仓库兼作自己的 QX 规则中心（仓库名仍是 `apple-policy`，改名会破坏已引用的 jsDelivr 地址）。每份清单一个文件，自带策略列。

| 文件 | 内容 | 条数 |
|---|---|---|
| `Apple.list` | 第 1 段 Apple 智能 32 条；第 2 段大流量 29 条直连；第 3 段其余 Apple 域名 1783 条 | 1844 |
| `Custom.list` | 自定义规则：直连例外、指定走节点、ChatGPT/Copilot 兜底 | 8 |

## 三段，顺序即优先级

| 段 | 策略 | 放什么 | 为什么 |
|---|---|---|---|
| Apple 智能 | `🍎 Apple 智能`（默认美国） | Siri 后端、ChatGPT 扩展、Private Relay、**地区判定**（`gs-loc*` / `configuration` / `bag.itunes` / `gspe*`） | 只有出口在支持地区，Siri 里才出现 ChatGPT；地区判定放这段是为了与「苹果服务」组的选态解耦——服务组手动切 DIRECT 时地区判定不再跟着掉回 CN |
| 大流量 | `DIRECT` | App Store 下载、系统更新、Xcode、Apple Music、iCloud 云盘/备份、地图瓦片 | 走代理会白烧节点流量，下载还会被节点带宽卡住 |
| Apple 服务 | `🍎 苹果服务`（默认美国） | 其余全部 | 推送、账户、商店 API 流量小；留在同一出口最省事 |

`DIRECT` 写在第三列，不需要额外的策略组。

## 为什么是一份

上游 `Apple.list` 有一条 `HOST-SUFFIX,apple.com`，它覆盖 `Apple-AI.list` 里的所有 `*.apple.com`。如果拆成多份文件，谁先命中谁生效，而 QX 对远程清单的先后顺序并不可靠——服务清单排在前面时，`gspe1-ssl.ls.apple.com` 会被直连（`https://gspe1-ssl.ls.apple.com/pep/gcc` 返回 `CN`）。

合成一份后，规则在文件内的顺序是确定的：Apple 智能 → 直连 → 服务。

## 引用

```ini
[filter_remote]

https://cdn.jsdelivr.net/gh/tankui-cq/apple-policy@main/Apple.list, tag=Apple, update-interval=86400, opt-parser=true, enabled=true
https://cdn.jsdelivr.net/gh/tankui-cq/apple-policy@main/Custom.list, tag=自定义, update-interval=86400, opt-parser=false, enabled=true
```

**不要加 `force-policy`**，策略由文件第三列决定。策略组名需与文件里一致：`🍎 Apple 智能`、`🍎 苹果服务`、`🤖 AI Platforms`、`节点选择`；`DIRECT` 是 QX 内置策略。

## Custom.list

放不进第三方清单的零散规则，按段落分：

| 段 | 例子 | 说明 |
|---|---|---|
| 直连例外 | `3.cn` | 京东推送短链，主站 `jd.com` 已在「国内网站」清单 |
| 指定走节点 | `exitgames.com`、`bnbstatic.com` | 默认会被「国外网站」接走，钉死到 `节点选择` |
| ChatGPT/Copilot 兜底 | `chatgpt.com`、`openai.com`、`copilot.microsoft.com` | 主清单失效时仍有固定出口 |

新增规则只改这个文件，QX 里「更新配置」就能生效，不用重新导入配置、不用换文件名。

策略组、`FINAL`、私网 IP 仍然只能写在配置里——QX 没有 `[policy_remote]`，而且清单拉取失败时私网规则会一起消失。

走 jsDelivr 是因为 `raw.githubusercontent.com` 在国内不稳定，仓库需要保持 public。

## 维护

```bash
python tools/build.py                                              # 从上游拉取并重新生成
python tools/build.py --apple 本地Apple.list --ai 本地Apple-AI.list   # 离线
```

上游：

- 服务规则 ← [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) 的 `Apple/Apple.list`
- AI 规则 ← [RocM301/Apple-Rule](https://github.com/RocM301/Apple-Rule) 的 `Apple-AI.list`
- 直连清单 ← [felixonmars/dnsmasq-china-list](https://github.com/felixonmars/dnsmasq-china-list) 的 `apple.china.conf`（在中国有 CDN 节点的 Apple 域名）

脚本把 `DOMAIN` / `DOMAIN-SUFFIX` / `DOMAIN-KEYWORD` 转成 `HOST` / `HOST-SUFFIX` / `HOST-KEYWORD`，并去掉被前面段覆盖的条目。

三个例外写在 `tools/build.py`：

- `EXTRA_AI`：上游没有、但 AI 链路要用的域名（现 14 条）。其中 4 条（`apple-cloudkit.com`、`p150-acsegateway.icloud.com`、`gs-loc-cn.apple.com`、`guzzoni-apple-com.v.aaplimg.com`）来自旧配置的本地规则，不补就会掉进 `HOST-SUFFIX,apple.com` 走直连；**末尾 3 条是地区判定**（`gs-loc.apple.com`、`configuration.apple.com`、`bag.itunes.apple.com`），上游把它们放在服务段、靠「🍎 苹果服务」默认美国才生效——服务组一旦被手动切成 DIRECT，GCC 立刻返回 CN、Siri 里的 ChatGPT 消失，而且从「🍎 Apple 智能」组完全看不出来，挪进 AI 段后与服务组选态解耦（2026-11-20）。
- `DROP_AI`：丢掉上游的 `HOST-KEYWORD,siri`，改用 `HOST-SUFFIX,siri.apple.com` 加 5 条精确域名。关键字规则在 QX 开「分流匹配优化」时可能被更具体的 `HOST-SUFFIX,apple.com` 压掉，5 个 Siri 后端会全部直连。
- `CHINA_TRAFFIC`：大流量直连段。`guzzoni` / `seed*` / `probe` / `gspe*` 在 `apple.china.conf` 里也有国内节点，但它们必须走美国，所以不能整份照搬。

`tools/overlap.py` 用于统计清单间的同键重复（QuanX 文档里 Spotify 21 条 / Twitter 25 条那组数字就是它算的）。

更新后若 CDN 仍返回旧内容：

```
https://purge.jsdelivr.net/gh/tankui-cq/apple-policy@main/Apple.list
```

## 注意

- 配置文件里不要写 Apple 域名规则。`[filter_local]` 会盖过远程清单，容易导致清单不生效。
- 分流只影响路由，不改变设备的 Apple 智能资格。
