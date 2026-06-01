# GZ-SYS-008 完工报告 — mp type-check 噪音清零

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（按指令不做 git 操作） |
| type-check 基线 | ✅ 改前 2 error（与 ticket 已知一致，无第三处） |
| type-check 终态 | ✅ exit=0 零 error |
| vitest | ✅ 114/114 全绿 |
| 零 any / 零 @ts-ignore | ✅ 真修类型 |

## 实现摘要

改前 `pnpm type-check` raw（2 error）：
```
src/components/biz/BizCustomerServiceFab.vue(92,5): error TS2322: Type 'string' is not assignable to type 'boolean'.
src/pages/login/index.vue(35,50): error TS2339: Property 'catch' does not exist on type 'void'.
```

| # | 文件:行 | 错误 | 修法（真修类型，无 any / 无 @ts-ignore） |
|---|---|---|---|
| 1 | `BizCustomerServiceFab.vue:92` | TS2322 string→boolean | `show-message-card="false"`（HTML 字符串字面量 `"false"`）→ `:show-message-card="false"`（v-bind 布尔字面量）。原意就是布尔 false，渲染语义等价。 |
| 2 | `login/index.vue:35` | TS2339 'catch' on void | `uni.switchTab({...}).catch(() => reLaunch)`（uni-app 类型里传 options 对象的 switchTab 返回 void，不能 .catch）→ 改用 uni-app 原生 `fail` 回调：`uni.switchTab({ url, fail: () => uni.reLaunch({...}) })`。fallback 逻辑等价（switchTab 失败→reLaunch，NO_TABBAR 策略下首页非 tab 的兜底）。 |

> 注：GZ-UI-001 已在同两文件做 JSDoc hex 清理与 D-1 换皮，本票仅动 #92 布尔绑定与 #35 回调，互不冲突（按 1→2→3 顺序，最后 type-check 看到全部三票改动）。

## AI 自测（Tier 1A）

### type-check（终态零 error）
```
> sensenran-guzi-miniapp@0.1.0 type-check
> vue-tsc --noEmit

=== type-check exit=0 ===
```
（无任何 error 行输出，exit=0）

### vitest（运行时行为不回归）
```
 Test Files  17 passed (17)
      Tests  114 passed (114)
   Duration  1.80s
```

### 改动后两文件无 any / @ts-ignore 残留
```bash
grep -nE ":\s*any\b|@ts-ignore|as any" src/components/biz/BizCustomerServiceFab.vue src/pages/login/index.vue
# 输出：(空) — 零 any / 零 @ts-ignore
```

## 风险提示 / 已知 issue

- 纯类型修复，运行时行为等价：`:show-message-card="false"` 与原 `"false"` 在 mp-weixin 渲染一致（原生 button 的 show-message-card 接受布尔）；`fail` 回调与原 `.catch` fallback 触发条件一致。
- 无 mp / 无微信原生能力 / 无 DB → **不进 Tier 2 人验**（仅 Tier 1A/1B），AI ✅ 即终态。

## 对下游 ticket 的提示

- mp `type-check` 现已是干净基线（0 error），后续 ticket 完工自测应保持 0；引入新 error 当票内清，勿留尾（D7x「测试期问题完整解决」原则）。

## §AI 测试段（kevin-qa 完工后追加）

（本环境不 spawn subagent；Tier 1B 由主线程集成 gate 处理。占位）
