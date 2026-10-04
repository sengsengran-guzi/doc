---
ticket: GZ-SNAP-404
track: SNAP-ADMIN
phase: D11
size: S
req_refs: [REQ-SNAP-014]
depends_on: [GZ-SNAP-403]
touches:
  - code/main/plus-ui/src/views/gz-jp/snap/term/**
  - code/main/plus-ui/src/api/gz-jp/**
  - code/main/plus-ui/src/lang/zh_CN.ts
  - code/main/plus-ui/src/lang/en_US.ts
  - code/main/plus-ui/e2e/gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/**
blueprint_refs:
  - UI:admin.snap_term
  - FIELD:gz_jp_snap_term.zh_term
  - FIELD:gz_jp_snap_term.term_type
  - FLOW:F-JP-05.step2
accept:
  - name: 词表 14070 段菜单 path/component 非空且父级是 14040
    form: MENU
    run: |
      Q() { docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "$1"; }
      Q "SELECT COUNT(*) FROM sys_menu WHERE menu_id=14070 AND menu_type='C' AND parent_id=14040 AND path<>'' AND component<>''" | grep -qx 1 && \
      Q "SELECT COUNT(*) FROM sys_menu WHERE menu_id BETWEEN 14071 AND 14079 AND menu_type='F' AND perms LIKE 'gz:jp:snap:term:%'" | grep -qE '^[3-9]'
    counterfeit: 菜单挂错父级或 path 为空 → 红
  - name: 词表 CRUD + 中文词唯一 + 「试一试」返回替换后的日文串 E2E
    form: API
    run: cd code/main/plus-ui && npx playwright test e2e/gz-jp/snap-term.spec.ts --reporter=line
    counterfeit: 新增重复中文词不报错（uk 未含 tenant_id 或未捕获）或「试一试」只回显原文 → spec 红
---

# GZ-SNAP-404 admin 代切词表

## §0 状态自检

1. GZ-SNAP-302 的 normalize 接口可调；菜单空号复查 14070–14079。

## What

1. 后端 `/system/gz/jp/snap/term`：list（按类型 / 启用 / 关键字筛）/ add / edit / remove / 启停；`zh_term` 唯一（撞 `uk_zh_term` 返回友好提示）；
   改动后清归一化用的词表缓存。
2. 页面照 gz-bean/store 范式；新增弹窗内「试一试」调 `POST /system/gz/jp/snap/term/normalize`。
3. 菜单 14070（C，`gz-jp/snap/term/index`）+ 按钮 14071–14079（`gz:jp:snap:term:query|add|edit|remove`），授权 owner。
4. 首批词条不由本卡造（运营在后台录入）；E2E 自己经接口建、测完经接口删。

## AC

- 两条 accept 绿；改词表后 mp 搜索立即用上新词（缓存已清）。
