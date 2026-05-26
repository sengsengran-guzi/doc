# <TICKET-ID> — 完工报告

> 由 kevin-coder agent 在完工时写。**禁止"已通过 / ok / 全部跑通"五字了事** — 必须贴 ≥ 3 个代码 block raw output（verification gap 翻车前兆）。

---

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| git clean | ✅ / ❌ | （如非 clean，说明哪些是本 ticket 改动） |
| 上游依赖 merge | ✅ / N/A | （如依赖 GZ-XXX-N，说明是否已 merge） |
| 关键类/表/API 存在 | ✅ | （列硬探的命令 + 输出） |
| 编译通过 | ✅ | （mvn compile / pnpm build） |
| 权威蓝图引用完整 | doc/10 §X / doc/11 §Y / doc/12 §Z | （任务卡引用的三份蓝图均已 Read，摘录关键约束） |
| ADR 已读 | <编号> 或 "无相关" | （如读了 ADR-0001，必须摘录关键决策） |
| 合同范围 | V1.0 / V1.1 | （从 02-需求拆解 §2 / §3 查） |

## 实现摘要

### 改动文件

```
（git diff --stat 输出）
```

### 新增产物

- 后端：
  - `ruoyi-modules/ruoyi-gz-<域>/.../XxxController.java`
  - `ruoyi-modules/ruoyi-gz-<域>/.../XxxServiceImpl.java`
  - `ruoyi-admin/src/main/resources/db/migration/V<时间戳>__<TICKET>-<desc>.sql`
- Admin：`plus-ui/src/views/gz-<域>/xxx.vue`
- 小程序：`miniapp/src/pages/<page>.vue`

## AI 自测（必须 ≥ 3 个代码 block）

### 编译

```
（mvn compile 或 pnpm build 的 raw output，含 BUILD SUCCESS / Time 行）
```

### 单测

```
（mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-<域> -am 的 raw output）
（含 Tests run: X, Failures: Y, Errors: Z）
```

### API 烟雾测试

```bash
# 请求
curl -X POST http://localhost:8080/api/gz/xxx \
  -H "Content-Type: application/json" \
  -d '{"key":"value"}'

# 期望
{
  "code": 200,
  "data": {...}
}

# 实际
（实际 curl 输出）
```

### DB 验证

```sql
mysql> SELECT COUNT(*) FROM gz_xxx WHERE ...;
+----------+
| COUNT(*) |
+----------+
|       N  |
+----------+
```

## 风险提示 / 已知 issue

- 风险 1：xxx（说明应对方案 / 推迟到哪个 ticket）
- 待 Kevin testing-human 关注：（如视觉 / 文案 / 微信侧需要真机的部分）

## 对下游 ticket 的提示

- 下游 GZ-XXX-NNN 实施时注意：（具体提示）
- （如适用）我留了哪些 TODO 给下游 ticket 处理

---

<!-- 如果 Kevin testing-human 失败 + AI revision 修复，下面追加 §revision-1 / §revision-2 等段 -->

## §revision-N（每轮闭环修复后追加）

### 问题
（从 tickets/<T>.md §revision 段复制问题清单）

### 改动
（git diff --stat 输出）

### 重新自测

```
（重跑 mvn compile / 单测 / curl / DB 的 raw output）
```
