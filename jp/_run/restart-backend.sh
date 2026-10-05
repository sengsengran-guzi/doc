#!/bin/bash
# 共享后端重启脚本（mkdir 锁防并发）：clean install 指定 gz 模块（默认全部 gz-*） → 杀 8080 → detached 起 spring-boot:run → 等启动成功
# 用法: restart-backend.sh [逗号分隔的模块列表，如 ruoyi-modules/ruoyi-gz-jp]
set -u
export PATH=/opt/homebrew/bin:$PATH
ROOT=/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/RuoYi-Vue-Plus
RUN=/tmp/sensenran-run; mkdir -p $RUN
LOCK=$RUN/backend.lock.d
for i in $(seq 1 120); do mkdir "$LOCK" 2>/dev/null && break; echo "waiting backend lock ($i)…"; sleep 5; done
[ -d "$LOCK" ] || { echo "LOCK TIMEOUT"; exit 3; }
trap 'rmdir "$LOCK"' EXIT
MODS=${1:-ruoyi-modules/ruoyi-gz-common,ruoyi-modules/ruoyi-gz-bean,ruoyi-modules/ruoyi-gz-user,ruoyi-modules/ruoyi-gz-news,ruoyi-modules/ruoyi-gz-ord,ruoyi-modules/ruoyi-gz-gacha,ruoyi-modules/ruoyi-gz-coupon,ruoyi-modules/ruoyi-gz-recycle,ruoyi-modules/ruoyi-gz-jp}
cd $ROOT || exit 2
mvn -q clean install -DskipTests -pl "$MODS" -am || { echo "INSTALL FAILED"; exit 4; }
mvn -q clean -pl ruoyi-admin >/dev/null 2>&1   # 清掉 target/classes/db/migration 幽灵副本
for p in $(lsof -tnP -iTCP:8080 -sTCP:LISTEN 2>/dev/null); do pkill -P $p 2>/dev/null; kill $p; done
pkill -f 'spring-boot:run -pl ruoyi-admin' 2>/dev/null
for i in $(seq 1 30); do lsof -tnP -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 1; done
LOG=$RUN/backend.log
nohup mvn spring-boot:run -pl ruoyi-admin > $LOG 2>&1 < /dev/null &
disown
for i in $(seq 1 120); do
  grep -q '启动成功' $LOG && { echo "BACKEND UP (commit $(git rev-parse --short HEAD)$(git diff --quiet HEAD -- ruoyi-modules ruoyi-admin/src || echo +DIRTY-WORKTREE), branch $(git branch --show-current))"; grep -E 'Successfully (validated|applied)|Migrating schema' $LOG | tail -5; exit 0; }
  grep -qE 'APPLICATION FAILED|FlywayException|BUILD FAILURE' $LOG && { echo "BOOT FAILED"; grep -nE 'ERROR|Exception|FAILED' $LOG | head -30; exit 5; }
  sleep 3
done
echo "BOOT TIMEOUT"; tail -40 $LOG; exit 6
