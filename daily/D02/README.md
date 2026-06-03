# D02 — 系统底座完工：微信登录 + 用户 + 客服 + OSS

> 日期：2026-05-28（周四）
> 阶段：V1.0 实施期 day 1（D01 GZ-SYS-001 已 ✅）
> 上一日：[D01](../D01/README.md) ｜ 下一日：[D03](../D03/README.md)

---

## 今日目标

- **主线 1**（用户身份）：mp 微信原生登录 → openId/unionId 落库 → 登录态持久化 → admin 端能查 C 端用户列表（GZ-SYS-002 + GZ-SYS-003）
- **主线 2**（基础能力）：客服入口全局浮层（mp 端 `<button open-type="contact">`）+ OSS 文件上传统一服务（GZ-SYS-004 + GZ-SYS-005）

完工后系统底座具备 4 项基础能力：「能登录」「能查用户」「能联系客服」「能传图」，为 D03 的 Admin 后台 + 拼豆主数据铺路。

## Ticket 清单（4 个，按依赖顺序）

| Ticket | 标题 | 复杂度 | 依赖 | 状态 |
|---|---|---|---|---|
| GZ-SYS-002 | 微信登录链路（C 端） | S | GZ-SYS-001 ✅ | pending |
| GZ-SYS-003 | 用户基础模型（C 端 + 后台读） | S | GZ-SYS-002 | pending |
| GZ-SYS-004 | 客服入口（全局浮层） | S | GZ-SYS-001 ✅ | pending |
| GZ-SYS-005 | 文件上传与对象存储对接 | S | GZ-SYS-001 ✅ | pending |

详见 `tickets/<TICKET-ID>.md`（任务卡）+ `reports/<TICKET-ID>.md`（完工后）。

**依赖说明**：
- SYS-003 强依赖 SYS-002（用户表 schema 必须先有微信登录字段才能落库）
- SYS-004 / SYS-005 与 SYS-002 / 003 互不依赖，可并行 spawn

## 派单方式

**整日触发**（推荐 — 主线程读本 README → 按依赖顺序 spawn 多个 kevin-coder）：
```
开始 d2
```

**单 ticket 触发**（如某 ticket revision 闭环 / 局部重做）：
```
@coder 做 D02/GZ-SYS-002
```

主线程动作：
1. 读 D02/README.md（本文件）+ 依赖图
2. **串行**：先派 GZ-SYS-002 → 完工后派 GZ-SYS-003（schema 依赖）
3. **并行**：与上面同时，可以另起 subagent 跑 GZ-SYS-004 + GZ-SYS-005（互无依赖）
4. 4 个 ticket 全部 ✅ → 主线程提示 Kevin testing-human + 日终 closing

## 今日特殊约束

- **GZ-SYS-001 D01 §AC 2 / §AC 3 未完工部分**（甲方主体的小程序 AppID / AppSecret 申请、微信支付商户号证书）今日**不阻塞**本日 4 个 ticket：
  - GZ-SYS-002 微信登录可用 **wxMOCK 短路**（miniapp `.env.development` 已配 `VITE_WX_APPID=wxMOCK`），后端登录接口在 dev profile 下走 mock 通道返回固定 openId
  - 真实 AppID 到位后切换 `.env.staging` 即可上 staging 联调
- **API 路径前缀约定**（CLAUDE.md §6 + dongjiaoshan 同款）：
  - admin 端：`/system/...` / `/gz/<域>/...`（走 sa-token user）
  - 小程序：`/app/gz/<域>/...`（走 sa-token mp-client，无 prefix 时拒绝）
- **i18n 强制**：mp 端字符串走 `t('xxx.yyy')` + zh-CN 默认；admin 端同样规则。即使是一个 toast 也不允许硬编码中文
- **不要 commit**：4 个 ticket 全部 ✅ + Kevin testing-human 通过后再统一 commit
- **DDL 文件命名**：本日 GZ-SYS-003 / GZ-SYS-005 会写 DDL，命名严格按 `V<yyyyMMddHHmm>__GZ-SYS-00X-<desc>.sql` 放 `ruoyi-admin/src/main/resources/db/migration/`

## 与昨日 reports 对账（D01）

D01 `summary.md` 抓"对下游 ticket 的提示"段：
- ✅ 6 个 ruoyi-gz-* 模块结构已就位，本日 ticket 在 `ruoyi-gz-common`（SYS-002/003/004/005 都属于通用域）下加 Controller/Service
- ✅ `application-dev.yml` 已配 `sensenran-dev-mysql:3307` / `sensenran-dev-redis:6380`，本日落 DDL 直接走 Flyway 自动跑
- ⏳ 阿里云 OSS bucket 尚未真实创建（启动费推进中），SYS-005 在 dev profile 用 MinIO 容器替代（`sensenran-dev-minio:9000`）
- ⏳ 微信小程序 AppID 未到位，SYS-002 用 wxMOCK 短路（详今日特殊约束）

## 完成判定（DoD）

- [ ] 4 个 ticket 任务卡 §revision 段空（无未闭环问题）
- [ ] 4 个 reports/<T>.md 写完（含 §0 自检 + §N 完工 + ≥ 3 个代码 block 自测 raw output）
- [ ] mvn install + plus-ui build:prod + miniapp dev:mp-weixin 三端全绿（任一红 → STOP）
- [ ] testing-human.md 全勾
- [ ] cat reports/*.md > summary.md 已生成

## 已知风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 | wxMOCK 短路与真实微信登录的契约偏差（如 unionId 缺失） | SYS-002 实施时把 mock 与真实路径分离到不同 Service impl，按 `wx.appid=wxMOCK` 路由；契约层接口一致 |
| R2 | SYS-003 用户表 schema 若不容纳 V1.1 字段（积分 / 等级 / 火花券）→ V1.1 需 ALTER | 接受：V1.0 不预先建 V1.1 字段（doc/11 §2.1 已明确"V1.0 schema 不含 V1.1 字段"），V1.1 用 ALTER |
| R3 | MinIO dev 容器与阿里云 OSS API 兼容性问题 | SYS-005 用 ruoyi 自带 `OssClient` 抽象层（兼容 minio/aliyun/qiniu），切换走配置项不动代码 |
| R4 | 4 个 ticket 同日全部 ✅ 但跨 ticket 集成（如 SYS-002 落库时 SYS-003 schema 未到位）| 严格按依赖图串行 SYS-002 → SYS-003；其他 2 个并行无依赖 |

---

## 日终 closing 命令

```bash
cd doc/daily/D02
cat reports/*.md > summary.md
# Kevin testing-human OK 后再 commit
git add -A && git commit -m "D02: 系统底座完工 GZ-SYS-002/003/004/005"
# 然后写 D03/README.md（D03 候选：GZ-ADMIN-001/002/004/005 + GZ-SYS-006）
```
