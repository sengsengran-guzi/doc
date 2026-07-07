# D20 — 拼豆 7.05 批改（排位 / 关闭重做 / 组单）

> 权威：[ADR-0018](../../_adr/0018-pindou-group-booking-preassign-closure-rework.md)
> 座位格 UI 评审留档：[design/mockup/_review/gz-bean-board-cell-compare.html](../../../design/mockup/_review/gz-bean-board-cell-compare.html)（定稿 = 分层双栏格 + 2 处糅合）

## 范围与顺序

甲方 7.05 三条 = 店员侧物理座位化。按 ADR 顺序分两波：

### 第一波（现在开工，分成对价内）
| Ticket | 层 | 内容 | 依赖 |
|---|---|---|---|
| GZ-BEAN-047 | 后端 | 排位 `preAssignSeat` / 取消排位 `unassignSeat` + 占用互斥扩含 reserved + no_show cron 清 seat_id | — |
| GZ-BEAN-048 | 后端+admin | 看板 current+next 两层 + 分层双栏格 cell UI + 列表改名「未排位客人」+ 核销用已排座 | 047 |
| GZ-BEAN-049 | 后端 | 关闭重做：`slot_quota_close` 加 weekday+sess_date可空 + 各小时预约数预览 + 批量关闭 + 配额查询停消费 `seat_closure` | — |
| GZ-BEAN-050 | admin | 引导式关闭页（桌型→某天→自由时段→显示各小时预约数→关闭数量 + 每周循环开关）+ 退休 seat_closure 页/menu | 049 |

047-048 与 049-050 两串可并行。

### 第二波（§8.5 谈钱后 / 第一波落地后启动，ticket 卡到时再建）
GZ-BEAN-051 组表 + booking.group_no ／ 052 submitPaidGroup 原子 N 子单+组支付+禁券禁促销 ／ 053 mp 数量 stepper+按 N 变灰 ／ 054 整组排位/核销/退款+组标签 ／ 055 组级支付回调+组退款。

## 权限 / menu
排位 / 核销 / 组单一律复用 `gz:bean:booking:verify`，**不新建 menu**（避 menu 撞号，memory `menu-id-collision`）。关闭重做复用现有 gz-bean 关闭权限段。
