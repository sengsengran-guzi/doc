# D<N> — Testing-human（Kevin 一人跑）

> 只做 AI 干不了的活：浏览器 UI / 微信开发者工具 / DB 客户端 / 代码 review / 产品 sense 主观判断。
> 命令式 / 可断言为真假的事（mvn / curl / mysql count）→ AI 在 reports/<T>.md 里贴 raw output，不在这跑。

---

## 0. 环境

- 后端跑起来：`mvn spring-boot:run -pl ruoyi-admin`
- Admin 跑起来：`cd code/main/plus-ui && pnpm dev` → 浏览器 http://localhost:80
- 小程序跑起来：`cd code/main/miniapp && pnpm dev:mp-weixin` → 微信开发者工具打开 `dist/dev/mp-weixin`

---

## 1. 今日 ticket 验收清单

### GZ-XXX-001 — <标题>

**关联 mockup**：design/mockup/<page>.html

**关联 AC**（从 tickets/GZ-XXX-001.md 复制）：
- [ ] AC 1：...
- [ ] AC 2：...
- [ ] AC 3：...

**测试动作**：
1. 浏览器打开 `<URL>` / 微信开发者工具 → 小程序首页
2. 操作：点击 X → 检查 Y
3. DB 验证：mysql 客户端 `SELECT * FROM gz_xxx WHERE ...`
4. mp 视觉遵循 C 设计系统（粗墨边 / 硬投影 / 朱红 / 网点），以 doc/tokens.md + doc/13 为准；admin 不评判视觉

**判定**：
- ✅ OK → 在 progress.md 标 ✅
- ❌ NOT OK → 在 `tickets/GZ-XXX-001.md` 的 `§revision` 段写"问题 N: 现象 / 期望"

---

### GZ-XXX-002 — <标题>

（同上格式）

---

## 2. 跨 ticket 联调（如有）

如果今日 ticket 之间有协作（如 GZ-SYS-001 微信登录 → GZ-USER-001 个人资料读取），单独跑一次：

1. 微信登录走通
2. 进入个人资料页 → 数据显示
3. 退出登录 → 再进入 → 应跳登录页

---

## 3. 视觉 / 文案 review

- mp 视觉遵循 C 设计系统（粗墨边 / 硬投影 / 朱红 / 网点），以 doc/tokens.md + doc/13 为准 ✅ / 偏离；admin 不评判视觉
- emoji 没乱用 ✅ / 滥用
- 中文文案没机翻味 ✅ / 像 GPT 风
- 主 CTA = `var(--c-red)`，不硬编码 hex（doc/tokens.md）✅ / 偏差

---

## 4. 性能 sense（主观感受）

- 小程序首页打开秒开？✅ / 卡
- API 响应 < 1s？✅ / 慢（哪个接口）
- DB 数据量级符合预期？✅ / 异常（如本该 10 条结果出来 1000 条）
