---
ticket: GZ-SYS-022
track: SYS
phase: D1
size: L
req_refs: [REQ-SYS-004]
depends_on: [GZ-SYS-020]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/pay/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/application*.yml
blueprint_refs:
  - FLOW:F-JP-00.step4
accept:
  - name: 下单与调起支付签名都用当前小程序的 appid
    form: API
    run: |
      cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
        -pl ruoyi-modules/ruoyi-gz-common -am \
        -Dtest=WechatPayMultiAppidTest 2>&1 | tail -5
  - name: 签名 appid 不再来自全局配置（防回归）
    form: API
    run: |
      ! grep -nE 'props\.getAppid\(\)\s*\+\s*"\\n"' \
        code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/pay/service/internal/WechatPayV3ClientImpl.java
---

# GZ-SYS-022 微信支付多 appid（配置 + 统一下单 + 调起签名）

## §0 状态自检

1. `sed -n '85,130p'` 看 `WechatPayV3ClientImpl` —— 确认 `:93` 统一下单、`:125` 调起签名两处 appid 读点仍在原位。
2. `docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "DESC gz_pay_channel"` —— 确认 `appid` 列存在（该列已有但目前是死数据）。

## What

**这是整个一期最致命的一处**：`WechatPayV3ClientImpl:125` 的调起支付 5 参签名写死全局 appid。
新小程序拿旧 appid 签出来的 paySign，`uni.requestPayment` **必然失败**，且微信侧报错含糊。

- `WechatPayProperties.appid` 标量 → Map（同 GZ-SYS-020 形态），或改读 `gz_pay_channel.appid`（**推荐**：该表已有此列，正好激活做真源）
- 统一下单（:93）与调起签名（:125）的 appid **一律从下单上下文取**，不再读全局配置
- `payer.openid` 与所用 appid 必须同源 —— 否则微信返「openid 与 appid 不匹配」

## AC

- 两个小程序各自下单、各自签名，单测覆盖「签名 appid 来自下单上下文」
- ⚠️ **真机 1 分钱验证推迟到 appid 回补阶段**（一期用 wxMOCK，拉不起真收银台）。
  本 ticket 以单测 + 现有小程序回归为准 close；真机验证列入 phase-plan 的 appid 回补清单
- 商户号不变（同主体可绑多 appid），回调 URL 共用（按 out_trade_no + business_type 路由，无需改）

## 风险提示

改的是线上正在跑的收款链路。**本 ticket 完工必须跑现有 miniapp 的拼豆真机支付回归**，不能只测新小程序。
