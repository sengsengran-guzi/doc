# D<N> — <一句话主题>

> 日期：2026-XX-XX（<周几>）
> 阶段：V1.0 | V1.1
> 上一日：D<N-1> ｜ 下一日：D<N+1>

---

## 今日目标

- 主线 1：...
- 主线 2：...

## Ticket 清单（2-4 个，按依赖顺序）

| Ticket | 标题 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|
| GZ-XXX-001 | ... | M | - | pending |
| GZ-XXX-002 | ... | S | GZ-XXX-001 | pending |

详见 `tickets/<TICKET-ID>.md`（任务卡）+ `reports/<TICKET-ID>.md`（完工后）。

## 派单示例

```
@coder 做 D<N>/GZ-XXX-001
```

## 今日特殊约束

（如有：哪个 mockup 缺口必须先补 / 哪个 ADR 必读 / 客户当天要 demo）

## 与昨日 reports 对账

（从 D<N-1>/summary.md 抓"对下游 ticket 的提示"段，确认今日不漏）

---

## 日终 closing 命令

```bash
cd doc/daily/D<N>
cat reports/*.md > summary.md
git add -A && git commit -m "D<N>: <主线>"
# 然后写 D<N+1>/README.md
```
