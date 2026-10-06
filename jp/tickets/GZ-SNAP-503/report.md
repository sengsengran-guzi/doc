# GZ-SNAP-503 完工报告

STATUS: DONE

COMMITS: backend `f74e8a4cf`；miniapp-jp `bbb98c6a9eb19df4996a145303c2d7272b003030`（task/D12；未push/merge）。MIGRATIONS: none。

## 实现

- 后端增加认证只读 `GET /app/gz/jp/snap/order/quote/{quoteId}`：require原报价，查已有商品缓存，显式返回externalId/titleZh/titleJa/public-price七字段。不调gateway、不签新quote，不返回rate/markup。提交金额与实时复查规则不变。
- confirm.vue按mode=snap进入单件代切确认，地址选择/新增与支付/result复用一期；原quoteId及expiresAt保留。公共金额展开三行，倒计时自然归零后按钮「重新报价」回对应详情；无缓存/空ID同样要求重新报价。确认勾选默认false，必须有地址。纯闸门/倒计时独立confirm.snap.logic.ts；confirm.logic.ts未改。
- 用户协议正文增加代切服务条款，五项均覆盖：抢到不可取消、失败连服务费全额原路退、到付差价多退少不补、卖家信息以实物为准、验货不过退款。**文案待甲方过目，staging草案；真机原生支付列入Kevin人验/GZ-SNAP-601。** 产品正文没有工作流术语。
- snap-checkout真实模拟器→8080→replay+fake→mockwx。checkout增加精确客户保护guard：私有mode600原快照，CAST AS CHAR后的全字段HEX，original profile/address/cart及audit逐字恢复；精确新订单/支付/回调/异步自造主图+MinIO对象清理。cleanup分段收集错误，继续其它清理，失败保留私有快照。

## ACCEPT

1. `node test/e2e/run.mjs snap-checkout`：最终**1/1 PASS**。preview未登录401，missing4123，两次GET原ID/期限相同、报价keys不变，无rate/markup；真实单品标题与三行合计4743分；未勾点提交无订单；临时按exact ID隐藏原地址后，已勾仍不可提交且无订单，flags finally恢复；实际60秒期限自然到期→重新报价→对应详情，重新点击CTA使用新报价下单，原新quoteId/expiresAt/ack落库；订单99101000075由mock回调paid、manual outbox=1，结果页「支付成功」。[raw](raw/snap-checkout.log)
2. `pnpm exec vitest run src/pages/order/confirm.logic.test.ts src/pages/order/confirm.snap.logic.test.ts`：**45/45 PASS（一期41+新增4）**。后端定向projection **2 tests, failures0/errors0/skipped0**。最终source定向eslint exit0，vue-tsc exit0。未机械重复绿单测。[raw](raw/verification.log)
3. `node test/e2e/run.mjs checkout`：**1/1 PASS**。一期实际购物车入口、地址新增真落库、只读商品、金额恰两行、勾选双向、99101000076 paid、支付结果回读与清车全过，随后原客户三表full-row+audit SHA256 before=after。[raw](raw/checkout-regression.log)

开发产物 `pnpm exec uni build -p mp-weixin --mode development` exit0，dist/build/mp-weixin指纹见verification。E2E之后补空quoteId防404分支及guard收集错误/异步图片精确清理，未重跑已绿flow；独立QA/root最终构建应基于当前commit（prod finalbuild仍由root统一一次）。共享8080已是最终后端代码，启动marker为提交前dirty；504共享restart会刷新HEAD。未起额外服务；模拟器串行，无真实煤炉请求。

## 装置调整与精确恢复

首轮产品所有断言通过，但fixture finally用HEX(number)按UTF8恢复，id14变成0xE字符串，恢复SQL失败。已改HEX(CAST(column AS CHAR))，重建原profile精确值（含-1 audit），从502已验证receipt恢复pricing原HEX/audit。最终轮与一期回归已证明全部原行/audit等同。首次错误SQL含资料，未存入报告raw；私有恢复SQL移除，raw只保留脱敏输出。

pricing恢复：config_id14040001、三项仍null、quoteTtlSec600、update_by1/update_time2026-10-06 16:50:24；adminAPI恢复缓存后exact回写，再adminAPI与详情quote4121验证两级读回。既有FX99030500002(boc)保留，仅删除本人99030500027/28。

本轮精确清理SQL WHERE均含tenant1001及以下确切业务键（非大量DELETE）：

| 轮次 | order/item ID | orderNo | out_trade_no |
|---|---|---|---|
| 首次snap | 99101000074 | JPO-20261006-000151 | JPO-20261006-000152 |
| 最终snap | 99101000075 | JPO-20261006-000153 | JPO-20261006-000154 |
| 一期回归 | 99101000076 | JPO-20261006-000155 | JPO-20261006-000156 |

`gz_jp_snap_item.active_order_item_id`仅按本轮item ID清；snap_purchase/jp_refund按本轮order_item_id；pay callback/refund/shipping/transaction按本轮out_trade_no；order_item按order_id+user_id14；order按id+order_no+user_id14。最终order/item/pay/callback/file均0。自有m503 replay/tmp/cache/quote清除并容器test不存在，不动旧fixture/locks。

首轮异步主图file69：`gz/2026/10/06/28eaf5278c7149b9b8c436f62f6aa1ea.jpg`；最终file70：`gz/2026/10/06/26e38facddc44a27a34ef6ed06c2c3fe.jpg`。按确切file ID+key+usage+create_time清文件行，MinIO仅rm此两个对象且mc stat拒绝，现有图片保留；测试临时mc凭据目录清除。guard从订单行原mainImageId且不在before集合确认所有权，后续QA直接复用。

OUT_OF_TOUCHES: none。后端4文件+MP10文件均在ticket声明路径内。权威FLOW:F-JP-06.step2/UI:mp.order_confirm.snap已由root同步doc@14359e9。

下游：504可复用snap-order.ts及guard；串行devtools。QA勿跑真煤炉/202历史live；定价临时测试仍须exact byte+audit复原。两个代码仓只剩既有backend日志tmp（未动），MP干净；doc报告/raw未commit。
