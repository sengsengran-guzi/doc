# D01 — 三端工程脚手架 + 云服务采购启动

> 日期：2026-05-27（周三）
> 阶段：V1.0 筹备期 / 实施期首日
> 上一日：（无，D01 是首日）｜ 下一日：D02

---

## 今日目标

- **主线 1**：搭建三端工程骨架（后端 6 个业务模块 + Admin 7 个业务目录 + 小程序 7 个占位页），三端各自能跑 hello world
- **主线 2**：本 ticket 同时识别"AI 干不了 / Kevin 自推进 / 等甲方"的事项，分线推进（云服务采购、微信小程序账号、微信支付证书）

## Ticket 清单

| Ticket | 标题 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|
| GZ-SYS-001 | 项目脚手架与云服务初始化 | M | 无 | in-progress |

D01 只跑这一个 ticket — 脚手架本身工作量大，且**所有后续 ticket 都依赖它**（doc/02-需求拆解.md 至少 8 个 ticket 标注 `依赖：GZ-SYS-001`）。

详见 `tickets/GZ-SYS-001.md`（任务卡）+ `reports/GZ-SYS-001.md`（完工后）。

## 派单示例

```
@coder 做 D01/GZ-SYS-001
```

## 今日特殊约束

- **JDK 版本**：本机仅 jdk-11 + jdk-20，**无 JDK 17 / 21**。Kevin 裁定 D2a：先用 JDK 20 试。若 ruoyi 5.6.1 父 pom 锁 source/release=17 与 JDK 20 不兼容报错 → **STOP 报 Kevin**，不要硬切 jdk
- **云厂商 = 阿里云**（不是腾讯云 — Kevin 当日裁定 C1）。`application-prod.yml` 配置阿里云 OSS / SMS / RDS（脚手架阶段占位 secrets，不连真实云）
- **GitHub 默认分支**：保留三端的 `5.X` / `ts` 默认，sensenran 工作在 `staging` 分支
- **不要 commit** — Kevin testing-human 通过后才 commit
- **dongjiaoshan 只读** — 母版可以读 + 抄 + rsync 复制改名，但绝对不修改 dongjiaoshan 任何文件
- **业务包名**：`org.dromara.gz.<域>.{controller,service,mapper,domain,dto}`（CLAUDE.md §6 #4）
- **表前缀**：`gz_<域>_<表>`（doc/04 v0.2 §1.3）

## 与昨日 reports 对账

D01 是首日，无昨日 reports。但筹备期 5/26 已经定型：
- doc/02-需求拆解.md 57 ticket 已完成
- doc/04 v0.2 架构 已升级完毕
- doc/10 / doc/11 / doc/12 v0.2 已稳定
- 三端 git repo 已 fork（staging 分支）

D02 起进入正式实施期，下游 ticket 候选：
- GZ-SYS-002 微信登录链路（mp + be，依赖 GZ-SYS-001）
- GZ-SYS-003 用户基础模型（依赖 GZ-SYS-002）
- GZ-SYS-004 客服入口（mp + admin 配置项，依赖 GZ-SYS-001）

---

## 日终 closing 命令

```bash
cd doc/daily/D01
cat reports/*.md > summary.md
# Kevin testing-human OK 后再 commit（按 CLAUDE.md §2 SOP）
git add -A && git commit -m "D01: 三端脚手架 + GZ-SYS-001"
# 然后写 D02/README.md
```
