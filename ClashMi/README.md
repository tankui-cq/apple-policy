# QuanX → Clash Mi 完整转换

把 `QuanX-20261120-6.conf`（含 `Apple.list` / `Custom.list` / Unbreak）整套分流搬进 Clash Mi。
**订阅只负责提供节点，规则和策略组全部钉在这个覆写文件里** —— 订阅刷新、换机场都不会冲掉规则。

## 文件

| 文件 | 作用 |
|---|---|
| `clashmi-override.yaml` | **主文件**。Clash Mi「自定义覆写」：23 个策略组 + 25 个远程规则集 + 1948 条规则 + DNS |
| `qx2clash.py` | 把 QX 格式清单转成 Clash 规则行的转换器，并原地刷新覆写文件里的生成段 |
| `README.md` | 本文件 |

`clashmi-override.yaml` 里 `# >>> GENERATED:xxx` 标记之间的内容由脚本生成，别手改；标记外的部分随便改。

## 原理（官方 FAQ + 客户端源码确认）

```
原始配置(订阅)  <-  自定义覆写(本文件)  <-  App 内置覆写
```

- 覆写对订阅是「覆盖」语义：本文件里的 `rules:` 整段替换订阅自带规则，`proxy-groups:` 整段替换订阅自带分组，
  而 `proxies:`（节点）不定义 → 订阅里的节点原样保留。这就是「节点跟着订阅走、规则跟着本地走」。
- 分组不写死节点名，用 `include-all: true` + `filter:` 正则（等价 QX 的 `server-tag-regex`），
  节点增删、改名都不用改规则。
- 一个订阅同时只能挂一个覆写：选了「自定义覆写」就不会再挂「内置-覆写」。挂了自定义覆写后，
  **App「核心设置-DNS」里的设置不再写入最终配置**（源码 `defaultConfigNoOverwrite()` 里 `DNS: null`），
  所以 DNS 写在本文件的 `dns:` 段。
- DNS 是「加密 + 明文 + 系统」混合（对齐 mihomo 文档 / App 默认）：IP 形式 DoH 在前（不需要引导解析），
  再域名形式 DoH、明文、`system`。只写 DoH 时，公司网/酒店网把 UDP53 拦掉会连 DoH 域名都解析不出来；
  只写明文时又会被劫持。混合后任何一层被拦都还有下一层。
- 另外三项对齐主流基线：`tcp-concurrent: true`（多 IP 并发握手，脏 DNS / 多 CDN 边缘时不会卡在坏 IP 上）、
  `sniffer.enable: true`（Clash Mi 在自定义覆写下 App 的嗅探开关不生效，必须写进配置）、
  `fake-ip-filter` 补齐 App 默认项（APNs 推送、B 站 P2P、NTP/STUN、Xbox 等）。
- **苹果服务组默认改为 DIRECT**：本文件 1948 条规则里有 1764 条指向它，原默认是「美国」，
  等于 iCloud 中国 / App Store / Apple Pay / APNs 全走美国节点，这是最容易造成「部分网站/功能异常」的一处。

## 导入步骤

1. **加订阅**：照常「➕ → 添加配置链接」，只把它当节点来源。添加时如果让你选「内置-覆写 / 内置-不覆写」，
   选哪个都行，下一步会改成我们的覆写。
2. **加覆写**：`设置 → 核心设置 → 覆写`（提示语是「原始配置<-自定义覆写<-App覆写」）
   → 右上角 ➕ → 「导入文件」选本文件；或者把本文件推到自己的仓库后用「添加配置链接」+ 自动更新间隔。
3. **挂到订阅**：`我的配置 → 该订阅 → 编辑配置 → 核心覆写` → 选中 `clashmi-override`
   （列表里「内置-覆写 / 内置-不覆写」是内置项，别选）。
4. **⚠️ 编辑配置里「规则」「代理组」两项保持为空**。那是「内置分流模板覆写」，
   一旦选了模板，内核会把规则整段换成模板规则，把我们覆写里的 rules 顶掉。
5. **TUN / 内网**：`核心设置 → TUN` 打开 TUN；把「排除本地网络（excluded routes）」打开，
   或手动排除 `192.168.0.0/16, 172.16.0.0/12, 10.0.0.0/8, 100.64.0.0/10, 224.0.0.0/4` ——
   对应 QX 的 `excluded_routes`，不排掉的话路由器管理页 / AirPlay / 投屏会走代理。
   TUN 地址段保持 App 默认 `172.19.0.1/30`；「IPv6」关闭（与 `dns.ipv6: false` 一致）；模式选 `规则`。
6. 启动，看「代理」页分组是否都有节点、「规则」页命中情况是否符合预期。

如果分组显示为空：说明内核版本不认 `include-all`，把该组的 `include-all: true` 换成
`include-all-proxies: true`（订阅节点是内联 `proxies:` 的话）或 `include-all-providers: true`（节点走 provider 的话）。

## QX → Clash Mi 对照

| QX | Clash Mi |
|---|---|
| `[policy] static=` | `type: select` + `proxies:` |
| `url-latency-benchmark= + server-tag-regex` | `type: url-test` + `include-all` + `filter`（`check-interval`→`interval`，`tolerance` 不变） |
| `img-url=` | `icon:` |
| `[filter_remote] force-policy=` + 清单 | `rule-providers`（blackmatrix7 的 **Clash 版** `rule/Clash/*.yaml`）+ `RULE-SET,name,策略组`。注意大清单是拆开发布的：`X.yaml` 只含关键词/IP，域名主体在 `X_Domain.yaml`（`behavior: domain`），两份都要挂 |
| `[filter_local]` | `rules:` 开头（本地优先，和 QX 一致） |
| `HOST-SUFFIX / HOST / HOST-KEYWORD` | `DOMAIN-SUFFIX / DOMAIN / DOMAIN-KEYWORD` |
| `HOST-WILDCARD` | `DOMAIN-REGEX`（glob 转正则，已锚定） |
| `IP6-CIDR` | `IP-CIDR6` |
| `GEOIP,CN` | `GEOIP,CN`（用来替代 ChinaIPs.list） |
| `[dns] server=` | `dns.nameserver` |
| `dns_exclusion_list` | `dns.fake-ip-filter` |
| `server=/域名/223.5.5.5` | `dns.nameserver-policy` |
| `udp_drop_list = 443` | `AND,((NETWORK,UDP),(DST-PORT,443)),REJECT` |
| `[rewrite_remote/local]` `[task_local]` `[mitm]` `[http_backend]` | 无对应（QX 专属脚本功能） |

## 和原配置的差异（逐条，都有原因）

1. **USER-AGENT 规则丢了 23 条**（全在 `Apple.list`）。Clash/mihomo 没有 UA 规则类型；
   而且 QX 侧 `[mitm]` 只解密 boxjs，这些 UA 规则本来也只对明文 HTTP 生效，实际等于没在用。
2. **「自动选择」的排除正则**：QX 用的是 `^(?!.*(剩余|到期|…)).*$` 负向断言，Go 正则不支持，
   改成内核自带的 `exclude-filter:`，语义相同（名字含这些词的伪节点全部剔除）。
   若你的版本仍把「剩余/到期」混进组里，说明 `exclude-filter` 没生效，改成白名单 `filter:`。
3. **国内兜底改成三层**（对齐 ACL4SSR / Loyalsoldier）：`china` / `china-domain`（域名）
   → `cncidr`（Loyalsoldier，约 9.6k 条中国 IP 段，`behavior: ipcidr`）→ `GEOIP,CN,DIRECT`。
   只靠 `GEOIP` 时，一旦 GeoIP 库缺失/过期，未收录的国内站就会掉进代理（蜜雪冰城 App/H5 就是这样）。
   `ipcidr` 规则集在 mihomo 里是合并后的 CIDR 集合，内存占用很小。
4. **`fallback_udp_policy = direct` 无对应**：mihomo 的 UDP 由节点协议决定，能转发就转发。
5. **`circumvent-ipv4-answer`（DNS 污染应答 IP 表）无对应**：mihomo 无此机制；fake-ip + 远程解析已经绕开大部分污染。
6. **Supercell 规则改了明确目标**：QX 那条远程清单没写 `force-policy`，靠清单自带策略列；
   这里明确指向 `Supercell` 组（成员 `DIRECT, 节点选择, REJECT`，默认直连）。
7. **`节点选择` 多了 `include-all`**：QX 里只能靠测速组自动选，现在可以在组里手动点具体节点。其余成员与顺序不变。
   同时给它加了与「自动选择」相同的 `exclude-filter`，避免「剩余流量/到期」等伪节点混进下拉。
8. **QUIC 丢弃规则**：从最前面移到 `GEOIP,CN` 之后、`MATCH` 之前——只丢弃「本来要交给代理」的 QUIC，
   国内直连的 HTTP/3 不再被误杀。用 hysteria2/tuic 想全量跑 QUIC，删掉那一行 `AND…REJECT`。
9. **Apple / Unbreak / Custom 三段内联了**（1821 + 34 + 8 条）。原 QX 是远程拉取，现在写在覆写文件里：
   好处是不用额外托管、不会因为 CDN 抽风丢规则；代价是上游更新要跑一次脚本（见下）。
   blackmatrix7 的清单仍是远程自动更新（间隔沿用 QX 的 update-interval，单位都是秒）。
   其中 AdvertisingLite / Global / China 采用「`X.yaml` + `X_Domain.yaml`」双文件（后者 `behavior: domain`），
   因为上游把这几份大清单的域名部分单独发布了；只挂 `X.yaml` 会丢掉 3 万多条域名规则。
   Netflix 额外挂 `Netflix_IP.yaml`（`behavior: ipcidr`，`RULE-SET` 带 `no-resolve`）补齐 IP 段。
10. **任务/脚本**：`[task_local]` 三个 `event-interaction`（流量查询、节点信息查询等）是 QX 独有 UI，
    Clash Mi 没有；`[rewrite_remote]` 那 6 条全部 `enabled=false`，没有实际损失。
11. **AWAvenue 用 Classical 版**：`AWAvenue-Ads-Rule-Clash.yaml` 是 domain 格式（裸域名），
    在 `behavior: classical` 下会全部解析失败；这里改用 `AWAvenue-Ads-Rule-Clash-Classical.yaml`。
12. **本地修正了两处上游过宽/不合适的规则**：
    - `time.apple.com` / `time-ios.apple.com` / `time-macos.apple.com` 显式 DIRECT（NTP 走 UDP，经代理常不通）；
    - `DOMAIN-SUFFIX,digicert.com` 收敛为只把 `ocsp/crl3/crl4/cacerts.digicert.com` 送「苹果服务」，其余直连。
13. **通用国外层改用主流清单**：`Global` + `Global_Domain`（blackmatrix7，含 `DOMAIN-KEYWORD,amazon/google`
    这类宽泛关键词）换成 Loyalsoldier `proxy`（约 2.7 万条纯域名）；另外补 `private`（局域网/路由器管理域名）
    和 `telegramcidr`（Telegram IP 段）。这样不会再因为关键词把 `amazon.cn` / `google.cn` 这类国内站误判到代理。

## 维护

上游清单更新后刷新内联段（PowerShell）：

```powershell
cd C:\Research\apple-policy\ClashMi
python qx2clash.py https://cdn.jsdelivr.net/gh/tankui-cq/apple-policy@main/Apple.list   --inject clashmi-override.yaml --marker APPLE
python qx2clash.py https://cdn.jsdelivr.net/gh/ddgksf2013/Filter@master/Unbreak.list   --inject clashmi-override.yaml --marker UNBREAK
python qx2clash.py https://cdn.jsdelivr.net/gh/tankui-cq/apple-policy@main/Custom.list  --inject clashmi-override.yaml --marker CUSTOM
```

- 改自定义规则：直接改 `# >>> GENERATED:CUSTOM` 段（或改仓库里的 `Custom.list` 再跑一次脚本），
  然后重进 Clash Mi 更新覆写即可 —— 和 QX 里「改 Custom.list + 更新配置」的流程一致。
- 把覆写文件推到仓库后用「添加配置链接」挂载：
  `https://cdn.jsdelivr.net/gh/tankui-cq/apple-policy@v20261126-2/ClashMi/clashmi-override.yaml`
  ⚠️ jsdelivr 的 `@main` 分支别名会缓存约 12 小时，`purge.jsdelivr.net` 也刷不掉别名解析；
  用 **tag**（或 pinned commit）URL 才能立即拿到新版本。每次改完配置会打一个新 tag。
- **iOS 内存**：官方 FAQ 提到 iOS 有内存上限，规则太多会「连上就断」。这里已经把最大的一份（ChinaIPs 1.9 万条）
  换成 GEOIP；AdvertisingLite / Global / China 的域名部分改用 `behavior: domain` 的 `*_Domain.yaml`
  （mihomo 用 succinct DomainSet 存储，比几万条 classical 规则省很多内存）。
  注意 **blackmatrix7 不发布 `.mrs`**，不要照抄 `format: mrs`；确实需要 mrs 可改用
  [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) 的 `geo/geosite/*.mrs`。

## 排错

| 现象 | 处理 |
|---|---|
| 部分网站 / App 功能异常 | ①「代理」页把 **🍎 苹果服务** 切 `DIRECT` 重试；②把 **🛑 广告拦截** 切 `DIRECT` 重试；③都不行，记下 `连接` 页那条的主机 / 规则 / 解析地址 |
| 推送、通话、B 站视频异常 | `dns.fake-ip-filter` 是否包含 `+.push.apple.com`、`+.bilivideo.com`、STUN 项（v20261126-2 已补） |
| 分组全空 | 内核不认 `include-all`，换 `include-all-proxies` / `include-all-providers` |
| 全部流量走直连 / 全部走代理 | 检查「编辑配置 → 核心覆写」是否真的选中了本覆写；再确认「编辑配置 → 规则」为空 |
| 规则页看不到我们的规则 | 同上：`rules` 被内置模板覆写顶掉了 |
| 断网或只有少数 App 能上网 | 确认「核心设置-TUN」地址段没被改乱（保持 App 默认 `172.19.0.1/30` 即可，不要手工填 `198.18.x`） |
| 路由器管理页打不开 | TUN 排除本地网络；`tplogin.cn` 等已在 `fake-ip-filter` 里，走真实解析到门户页再跳本地 |
| 「自动选择」里有「剩余流量/到期」 | `exclude-filter` 没生效，见差异说明第 2 条 |
| 某清单 404 | jsdelivr 偶发抽风，换个时间重试；或该分类在 blackmatrix7 的 `rule/Clash/` 下改名，改 `url` 即可 |
