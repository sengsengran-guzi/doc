---
ticket: GZ-SNAP-501
track: SNAP-MP
phase: D12
size: L
req_refs: [REQ-SNAP-002, REQ-SNAP-003, REQ-SNAP-012, REQ-SNAP-013, REQ-SNAP-045]
depends_on: [GZ-SNAP-405]
touches:
  - code/main/miniapp-jp/src/pages.json
  - code/main/miniapp-jp/src/pages/snap/**
  - code/main/miniapp-jp/src/static/tabbar/**
  - code/main/miniapp-jp/src/api/gz-jp/**
  - code/main/miniapp-jp/src/locale/**
  - code/main/miniapp-jp/src/components/biz/**
  - code/main/miniapp-jp/test/e2e/flows/**
blueprint_refs:
  - UI:mp.snap_search
  - UI:mp.snap_search.input
  - UI:mp.snap_search.result_grid
  - UI:mp.snap_search.sort
  - UI:mp.home.snap_entry
  - UI:global.theme
accept:
  - name: tabbar 三格（首页 / 煤炉 / 我的）且煤炉图标两态文件存在
    form: API
    run: |
      cd code/main/miniapp-jp && node -e "const s=require('fs').readFileSync('src/pages.json','utf8').replace(/\/\/.*$/mg,''); \
        const t=JSON.parse(s).tabBar.list.map(x=>x.text).join(','); if(t!=='首页,煤炉,我的'){console.error(t);process.exit(1)}" && \
      test -s src/static/tabbar/mercari.png && test -s src/static/tabbar/mercariHL.png
    counterfeit: tabbar 顺序写成 [首页, 我的, 煤炉]、或选中态图标缺失 → 红
  - name: 模拟器 E2E：煤炉 tab 可达、空态热门词、搜索出网格、粘贴链接直跳详情、日本服务挂掉时显示空态不白屏
    form: API
    run: cd code/main/miniapp-jp && node test/e2e/run.mjs snap-search
    counterfeit: 粘贴 jp.mercari.com/item/m123 仍当关键词去搜，或上游不可用时页面白屏 → flow 红
---

# GZ-SNAP-501 mp tabbar 三格 + 煤炉搜索页

## §0 状态自检

1. GZ-SNAP-302 的 `/app/gz/jp/snap/search` `/hot-terms` 可调（匿名）。
2. 读 `UI:mp.snap_search`、`design-options/README.md` 二期「设计权威」节（内容块来源）、`mp-snap-search.md`（方案 B）。
   `snap-review.html` 只看方案 B，A / C 是被否决方向。
3. token 真源 `src/style/c-tokens.scss` + `uno.config.ts`；页面只用 `components/biz/Biz*` + `var(--c-*)`，不直接撒 `<wd-*>`，不硬编码 hex。
4. 现有 `static/tabbar/home.png` / `me.png` 的尺寸与线条风格（新图标照它画）。

## What

1. 图标：按 home / me 的线性风格与像素尺寸画「煤炉」一组（建议购物袋 + 搜索放大镜意象，不用煤炉商标），
   常态色同现有灰、选中态品牌绿；产出 `mercari.png` / `mercariHL.png`（REQ-SNAP-045：甲方日后可替换）。
2. `pages.json`：新增 `pages/snap/index`（tabbar 页）；tabBar.list 改 [首页, 煤炉, 我的]。
3. 搜索页 `pages/snap/index.vue`（方案 B）：
   - 一个输入框；提交时后端若返回 `redirectItemId` 直接 `navigateTo` 详情；返回 `SNAP_SHOPS_UNSUPPORTED` 时提示「暂不支持煤炉 Shops 商品」；
   - 空态：热门词 chips（`/hot-terms`）+ 贴链接提示；
   - 结果两列网格：主图 1:1 + 中文标题两行截断 + 人民币参考价（主色）+ 日元小字 + manual 商品「需人工确认」角标；排序三选一；上拉分页；
   - `stale=true` 时顶部一行「显示的是稍早的结果」；`SNAP_UPSTREAM_DOWN` 显示「煤炉暂时访问不了」空态。
   需要的新原子组件进 `components/biz/`（如 `BizSnapCard`），前缀 Biz。
4. 文案走 locale（新增 `snap.zh-CN.ts`），不混 emoji。
5. E2E flow `test/e2e/flows/snap-search.mjs`（数据来自日本服务回放样本集，不打真煤炉）。

## AC

- 两条 accept 绿；`pnpm type-check` / `lint` / vitest 绿；一期 `node test/e2e/run.mjs all` 不回归。
- 新页首版视觉进 Kevin 人验列（Tier 2：设计首版拍板），功能以 AI E2E 为准。
