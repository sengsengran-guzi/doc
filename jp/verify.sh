#!/usr/bin/env bash
# L1 回归包原子 —— 谷子宇宙拼团（日本代购一期）
# 用法：bash doc/jp/verify.sh [域]    例：bash doc/jp/verify.sh jp
# 退出码 0 = 全绿。每个 ticket 的 accept 沉淀进来后，任务 QA 门在确定性快照上全量重放。
#
# ⚠️ 本脚本**只覆盖 dev 本机环境**（硬编码 dev 容器名 / 库名 ry-vue / localhost:8080 / ~/.m2 里的 jar）。
#    它是「dev 回归包」，**不是** staging/prod 验收工具 —— 那两套要走各自的环境（见 .dsh/knowledge/deploy.md）。
#    guard_env 会在环境对不上时直接 FAIL，不让它在错的环境里跑出「全绿」的假信号。
set -uo pipefail

MYSQL="docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e"
API_BASE="http://localhost:8080"
FAIL=0

# ── 断言 -1：环境守卫（先于一切断言）────────────────────────────────
# 只要不是「本机 dev 三件套」就拒绝跑：跑在别处得到的绿毫无意义，而一次误读的绿比红更贵。
guard_env() {
  if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'sensenran-dev-mysql'; then
    echo "  ✗ [env] 未找到 dev 容器 sensenran-dev-mysql —— 本脚本只用于本机 dev，不在目标环境执行"
    return 1
  fi
  if ! curl -s --noproxy '*' -o /dev/null -m 5 "$API_BASE/actuator/health" 2>/dev/null; then
    echo "  ✗ [env] $API_BASE 无响应 —— 先本机起后端（mvn spring-boot:run -pl ruoyi-admin，dev profile）"
    return 1
  fi
  echo "  ✓ [env] 本机 dev（sensenran-dev-mysql + $API_BASE）"
}

# ── 断言 0：反 stale（必跑前置守卫，不是可选）──────────────────────────
# 被测产物版本对不上就直接 FAIL，不许在旧 jar / 旧 dist 上断言
guard_fresh() {
  local jar
  jar=$(ls -t ~/.m2/repository/org/dromara/ruoyi-gz-jp/*/ruoyi-gz-jp-*.jar 2>/dev/null | head -1)
  if [ -z "$jar" ]; then echo "  ✗ [stale] ruoyi-gz-jp jar 不存在，先 mvn clean install"; return 1; fi
  local src_newest
  src_newest=$(find code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp -name '*.java' -newer "$jar" 2>/dev/null | head -1)
  if [ -n "$src_newest" ]; then
    echo "  ✗ [stale] 源码比 jar 新（$src_newest），必须 mvn clean install 后重跑"; return 1
  fi
  echo "  ✓ [fresh] jar 版本新鲜"
}

# ── 三个断言原子 ────────────────────────────────────────────────────
db()   { # db "说明" "SQL" "期望值"
  local got; got=$($MYSQL "$2" 2>/dev/null | tr -d '[:space:]')
  if [ "$got" = "$3" ]; then echo "  ✓ $1"; else echo "  ✗ $1 — 期望 [$3] 实得 [$got]"; FAIL=1; fi
}
api()  { # api "说明" "路径" "jq 表达式"   —— 必须断返回体内容，不是只断状态码
  local resp; resp=$(curl -s -H 'clientid: mp-applet-gz-jp' "$API_BASE$2" 2>/dev/null)
  if echo "$resp" | jq -e "$3" >/dev/null 2>&1; then echo "  ✓ $1"
  else echo "  ✗ $1 — 响应不满足 $3"; FAIL=1; fi
}
json() { # json "说明" "文件" "jq 表达式"
  if jq -e "$3" "$2" >/dev/null 2>&1; then echo "  ✓ $1"; else echo "  ✗ $1"; FAIL=1; fi
}

echo "── 断言 -1：环境守卫（dev 专用）──"
if ! guard_env; then
  echo ""
  echo "❌ verify.sh 拒绝在非 dev 本机环境执行 —— 本脚本是 dev 回归包，不是 staging/prod 验收工具"
  exit 2
fi

echo "── 断言 0：产物新鲜度 ──"
guard_fresh || FAIL=1

echo "── L1：建表与公共字段 ──"
for T in gz_jp_event gz_jp_product gz_jp_cart_item gz_jp_order gz_jp_order_item; do
  db "$T 公共字段全集齐(7)" \
     "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='ry-vue'
      AND table_name='$T' AND column_name IN
      ('create_by','create_time','update_by','update_time','create_dept','del_flag','tenant_id')" "7"
done

echo "── L1：跨表对账（禁自造数据自证，打在真 seed 上）──"
db "订单总额 == 行金额之和（无运费项）" \
   "SELECT COUNT(*) FROM gz_jp_order o WHERE o.del_flag='0' AND o.total_amount_cent <>
    (SELECT COALESCE(SUM(i.amount_cent),0) FROM gz_jp_order_item i
     WHERE i.order_id=o.id AND i.del_flag='0')" "0"
db "行金额 == 单价 × 数量" \
   "SELECT COUNT(*) FROM gz_jp_order_item WHERE del_flag='0'
    AND amount_cent <> unit_price_cent * qty" "0"
db "已退款行金额 == 该行金额（行级退款，非整单）" \
   "SELECT COUNT(*) FROM gz_jp_order_item WHERE del_flag='0'
    AND refund_status='refunded' AND refund_amount_cent <> amount_cent" "0"
db "delivered 行必有快递编码与单号" \
   "SELECT COUNT(*) FROM gz_jp_order_item WHERE del_flag='0' AND fulfill_status='delivered'
    AND (tracking_no IS NULL OR tracking_no='' OR carrier_code IS NULL OR carrier_code='')" "0"
db "同一运单号下的行状态一致（单号即包裹标识）" \
   "SELECT COUNT(*) FROM (SELECT tracking_no FROM gz_jp_order_item
    WHERE del_flag='0' AND tracking_no IS NOT NULL AND tracking_no<>''
    GROUP BY tracking_no HAVING COUNT(DISTINCT fulfill_status)>1) x" "0"
db "gz_user 无空 app_id（多 appid 隔离）" \
   "SELECT COUNT(*) FROM gz_user WHERE app_id IS NULL OR app_id=''" "0"

echo "── L1：C 端接口契约 ──"
api "场列表结构完整且不下发 draft" "/app/gz/jp/event/list" \
    '.rows | length >= 0 and ([.[] | select(.status=="draft")] | length == 0)'

echo ""
[ $FAIL -eq 0 ] && echo "✅ verify.sh 全绿" || echo "❌ verify.sh 有失败项"
exit $FAIL
