# D11 — Progress

> V1.2 快赢 + 拼豆地基 + 资料/登录态地基。**4 ticket 全 Tier 1A+1B ✅ 收口。**

---

| Ticket | 标题 | 端 | AI 自测(1A+1B) | 人验(Tier2) | revision 轮次 | 状态 |
|---|---|---|---|---|---|---|
| GZ-ORD-110 | 预购下线（屏蔽 admin + mp 入口，保留代码） | admin+be+mp | ✅ | — 无（纯入口屏蔽，DB+Playwright 已验） | 0 | ✅ done |
| GZ-USER-005 | gz_user.wechat_id 字段 + mp 资料页录入 | be+admin+mp | ✅ | ⬜ 待批 | 0 | ✅ done |
| GZ-USER-006 | 微信资料完善（chooseAvatar+nickname 持久化）+ 登录态保持 | be+mp | ✅ | ⬜ 待批（头像昵称持久化 + 登录态续期） | 0 | ✅ done |
| GZ-BEAN-013 | 座位类型配额配置（admin 配数量/单价 + 废弃 A1-A10） | be+admin | ✅ | — 无 | 2 | ✅ done |

**Tier 1B 验证铁证**（kevin-qa 起真 app 跑 Flyway + curl + Playwright）：
- **Flyway**：5 迁移 0600/0610/0620/0630/0631 全 apply 成功，无 checksum/语法/dict_id/menu_id 冲突。
- **ORD-110**：DB 验 preorder 9100-9112 全 `visible='1'` 隐藏、聚合 11007-11009 全 `'0'` 显示（一票否决守住）；Playwright nav 无预购菜单、有订单管理+扭蛋；mp 首页/orders 无预购入口。
- **USER-005/006**：`gz_user.wechat_id` + `avatar_image_id` 列在；profile 录入回显；token 静默续期不踢人；mp vitest 308 过；无 getUserProfile。
- **BEAN-013**（revision-2 后）：add single `200` / 重复 UNIQUE 拒 / vip_room @Pattern 拒 / GET listByStore priceYuan=15.00 / PUT / DELETE 软删 全 ✅。

**主线程介入修的 coder bug（reports 已记）**：
1. **ORD-110 `visible` 反向**：coder 写 `SET visible='0'`（ruoyi '0'=显示），改 `'1'` 才隐藏。
2. **BEAN-013 座位 perm 403 回归**：coder 撤了 6021(seat:list) → config seat tab loadSeats 403；改为保留 6021 只读，仅撤 6022-6025。
3. **BEAN-013 字典查询坑 ×2 处**（2 轮 revision）：service `getDictLabel` + Bo `@DictPattern` 均查系统字典 `tenant_id='000000'` 在租户 1001 查不到 → 改硬编码 `Set` + `@Pattern` 正则（详 [[ruoyi-menu-dict-gotchas]]）。

**过程异常**：3 条并行 coder 线，线 B/C 中途截断 + SendMessage resume 进坏状态（空转 / tool-call 解析失败）→ 主线程接管 ORD-110/BEAN-013 收尾（含上述 bug 修复 + BEAN-013 plus-ui 页/api/i18n 补全）。

---

## 人验列待批（Tier 2 批量，Kevin 自定节奏集中跑）

- **GZ-USER-005** ⬜：mp 底部 tab「我的」→「个人资料」→ 录入微信号 → 保存 → 重进资料页回显。
- **GZ-USER-006** ⬜：同页用 chooseAvatar 选头像 + 填昵称 → 保存 → 重进回显（头像+昵称+微信号）；长时间后再进**不弹重新登录**（token 静默续期）。

（GZ-ORD-110 + GZ-BEAN-013 纯 admin/后端，AI Tier 1A+1B 全 ✅ 即终态，无人验。）

---

## 下游解锁（D12+）

- **GZ-BEAN-013**（config quantity + seat_type 字典）→ D12 GZ-BEAN-014：付费列 + seat_type ALTER + 按 booking 计数防超卖（vs quantity）+ 余量查询接口 + 旧数据迁移（单笔单时段，无子表）。
- **GZ-USER-005**（wechat_id）→ D13 GZ-BEAN-015 拼豆付款前采集预填。
- **GZ-USER-006**（资料持久化 + sa-token 长效/静默续期）→ 全局受益（拼豆/回收付款前采集复用已持久化头像昵称；登录态贯穿 V1.2 各 mp 流）。

## 阻塞 / 风险

无遗留阻塞。BEAN-013 字典坑根因已记 [[ruoyi-menu-dict-gotchas]]，待 closing 写进 kevin-coder §0 自检防复发。
