# D7x — Progress（D1-D7 测试集中修复批次）

> 性质：非顺序 daily，是 Kevin 跑 D1-D7 批量人验发现问题的集中修复批次（ADR-0004 落地 + 完整闭环）。
> §一 8 条测试期内联修复已记录在案（README）。本表跟踪 §二「待派发清单」整批实现。
> 主题：核销搬 mp + mp 管理端权限底座 + 上线前视觉收口。**零 V1.1 推诿**。

---

| Ticket | 标题 | 端 | AI Tier 1A | 集成 gate | 人验 | 状态 |
|---|---|---|---|---|---|---|
| GZ-SYS-007 | mp 管理端权限底座（AC1-8） | 后端+mp+admin | ✅（前批已交付） | ✅ | N/A | ✅ done · 终态 |
| GZ-SYS-007 | └ AC9 停用自动踢 + AC10 owner 绑定管理 | 后端+admin | ✅ 切面单测7 + bind单测7 + live 端到端 | ✅ install 绿 / Flyway 5060-5063 | N/A 纯后端+admin | ✅ done · 终态 close |
| GZ-BEAN-011 | mp 扫码核销（店员端） | 后端+mp | ✅（前批已交付） | ✅ | ⬜ 真机扫码 | ✅ AI done · 待真机闭环 |
| GZ-BEAN-012 | 顾客核销码真二维码（被扫端） | mp | ✅ BizQrCode.test 4/4 | ✅ vitest 114/114 | ⬜ 011×012 真机联测 | ✅ AI done |
| GZ-UI-001 | mp 视觉 token 收口 + 客服浮层换皮 | mp | ✅ AC5 gate 零输出 / type-check 0 | ✅ vitest 114/114 | ⬜ 视觉契合（FAB/竹绿/鸟金） | ✅ AI done |
| GZ-SYS-008 | mp type-check 噪音清零 | mp | ✅ type-check exit 0（2 error→0） | ✅ | N/A 纯类型 | ✅ done · 终态 close |
| GZ-UI-002 | tabbar 3 套 C 风描边图标 | 设计+mp | ✅ 6×80×80 PNG 三形各异 | ✅ build 重生成 pages.json | ⬜ 真机看图 + ⚠️ Tier-3 视觉签字 | ✅ AI done · 待视觉签字 |

**状态枚举**：pending / in-progress / ai-testing / human-testing / revision-X / ✅ done / 🚫 blocked

---

## 主线程集成 gate（DoD，三 agent 并行完工后亲跑）

| 项 | 命令 | 结果 |
|---|---|---|
| 后端集成 install + test | `mvn install -DskipTests=false -pl ruoyi-gz-common -am` | **BUILD SUCCESS** · 61 单测 0 fail · ruoyi-gz-common-5.6.1.jar 已装 ✅ |
| Flyway 菜单迁移 | 启动自动跑 `V202606051100` | ✅ menu 5060-5063（店员绑定管理 + 3 权限按钮）· owner(100) 授权 4 / staff(101) 0 |
| AC9 切面 live | owner 停用 sys_user 101 | ✅ 切面日志「停用 sys_user=101 → 踢出 1 个 mp 会话」· 同店员 token /app/gz/staff/me → 401 |
| AC10 绑定 live | 6 场景 curl | ✅ list/candidates/bind/unbind + 绑不存在 sys_user→500 + 店员调 owner 端点→403 |
| Admin 构建 | `pnpm build:prod` | ✅ dist 产出（含 staff-binding chunk） |
| mp type-check | `pnpm type-check` | ✅ **0 error**（改前 2：FAB TS2322 + login TS2339，已真修，零 any / 零 @ts-ignore） |
| mp vitest | `pnpm vitest run` | ✅ **114/114**（17 文件，含 BizQrCode 4/4） |
| mp 构建 + pages.json 重生成 | `pnpm build:mp-weixin` | ✅ exit 0 · dist app.json tabBar 三 icon 各异（home/bean/me+HL）· 6 图入 dist/static/tabbar · src/pages.json 已重生成（注：`uni build` 尾部自动唤 wechat devtools cli 预览会挂起，非构建失败，已 kill 预览步，devtools GUI 未动） |
| UI-001 AC5 gate（修正正则） | `grep -rnE "var\(--c-(font-(sm\|lg\|xs\|body\|h1\|h2\|hero)\|ink-[0-9]{2}\|accent)" src` | ✅ 零输出（伪 token 清零，91 处合法 --c-ink-2/3 未误伤） |
| 旧 brand hex 残留 | `grep -riE "ff6b81\|faad14\|e5e0d5" src` | ✅ 零输出 |
| tabbar 图标 | 6×80×80 PNG | ✅ home/bean/me + HL，三形各异（opaque_px 1714/1653/1448），脚手架 example/scan/personal 已删 |

---

## ⭐ D7x 关键决策 / 修正（主线程）

1. **编排 = 3 文件互斥并行 agent**：A=后端(SYS-007 AC9/10) ∥ M=mp(BEAN-012→UI-001→SYS-008 **串行**，保证 type-check 最后跑见全部改动) ∥ D=designer(UI-002)。项目非 git repo + 无 worktree 隔离 → 靠文件作用域互斥防并行丢改动。
2. **BEAN-012 实际范围比卡片小**：`BizQrCode.vue` 前批（BEAN-005）已建、detail.vue 已用真 QR，本票**只剩 success.vue** 占位假网格换 `<BizQrCode>` + @fail 兜底。
3. **AC9 = Spring AOP 切面**（`SysUserStaffKickoutAspect` 放 gz-common，纯 `execution(FQN)` 切 ruoyi `SysUserServiceImpl.updateUserStatus/deleteUserByIds`，**不 import ruoyi-system、零新增模块依赖、不改 ruoyi 源码** 守铁律#1）→ 复用已就绪 `kickoutByStaffUserId`。切面仅对经 Spring 代理的外部调用生效（admin 标准停用入口已 live 证实）。
4. **UI-001 AC5 正则缺陷修正**（复盘优先级 §1 改权威 spec）：原 `ink-[0-9]`（1 位）误伤 91 处合法 `--c-ink-2/3`；伪 token 实为 2 位 `--c-ink-60` → 收紧为 `ink-[0-9]{2}`。已回改 ticket 卡 AC5 + 注明原因。**后续回归 gate 模板用 2 位数版，勿退回 1 位数。**
5. **UI-002 无 SVG 光栅化器**（sharp/canvas/magick/inkscape 全无，仅 pngjs）→ designer 写 `scripts/gen-tabbar-icons.mjs`（pngjs + 自写极小光栅器）生成几何 C 风图标。**⚠️ 这是 AI 手画几何图标，最终美术精度属 Tier-3 视觉签字（Kevin / 真设计师走查）**；真设计师精修时同名 drop-in 覆盖 6 张 PNG 即可（无需碰 config.ts）。

---

## ⏳ 待 Kevin / 部署侧动作

1. **UI-002 视觉签字（Tier-3）⚠️**：真机底部看 3 tab 图标是否各异可辨 + 选中态朱红；AI 几何图标美术精度是否达 C 系统粗描边硬朗标准 —— 不达标则真设计师精修（同名 drop-in）。**这是本批次唯一需要人拍板视觉的点。**
2. **批量人验（Tier 2，mp 真机）**：
   - BEAN-012 + BEAN-011：011×012 真机扫码核销端到端闭环（顾客 success/detail 出真 QR → 店员扫 → 核销成功）
   - UI-001：FAB 朱红硬投影 / verify-scan 竹绿成功态 / me 鸟金店员徽章 视觉契合度
3. **AC10 admin staff-binding 页 Playwright E2E 形式化确认**（功能层，本环境无 Agent 工具未跑 kevin-qa；coder 已 live curl 6 场景等价覆盖）。
4. **环境注意**（live 测 8080 用）：本机 `http_proxy=127.0.0.1:1081` → curl 须清代理 env 否则 HTTP 000；MySQL dev 端口 3307 / 密码 root / 库 ry-vue；admin 登 `gz_owner/gz_owner123!` 租户 1001。

## 阻塞 / 风险

- 无功能性阻塞。三 agent 全 done，集成 gate 全绿（mp build 待确认尾项）。
- AC9 切面 fallback：批量脚本直连 DB 停用绕过 Spring 代理则切面不触发 → fallback 是下次登录 resolve 降级 + owner 手动 kickout 端点（已就绪）。正常 admin 停用入口走代理，已 live 证实自动踢。

## menu_id 占用更新

GZ-SYS 段新占 **5060-5063**（店员绑定管理）；下游 GZ-SYS ticket 选号避开 5050-5055 + 5060-5063。
