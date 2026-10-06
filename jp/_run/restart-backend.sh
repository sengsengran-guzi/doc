#!/bin/bash
# 共享后端重启脚本（mkdir 锁防并发）：clean install 指定 gz 模块（默认全部 gz-*） → 杀 8080 → detached 起 spring-boot:run → 等启动成功
# 用法: restart-backend.sh [逗号分隔的模块列表，如 ruoyi-modules/ruoyi-gz-jp]
set -u
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export PATH=/opt/homebrew/bin:$PATH
ROOT=/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/RuoYi-Vue-Plus
# Local dev only: use the existing ignored gateway secret unless the caller supplied one.
# Parse the one key as data; never source .env as shell code or print credentials.
if [ -z "${GZ_JP_GATEWAY_SECRET:-}" ] && [ -f "$ROOT/../mercari-gateway/.env" ]; then
  GZ_JP_GATEWAY_SECRET=$(/opt/homebrew/bin/python3.11 - "$ROOT/../mercari-gateway/.env" <<'PY'
import sys
from pathlib import Path
for line in Path(sys.argv[1]).read_text().splitlines():
    key, sep, value = line.strip().partition('=')
    if sep and key == 'GATEWAY_HMAC_SECRET':
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if len(value) < 16:
            raise SystemExit('Local gateway secret is missing or too short')
        print(value)
        break
else:
    raise SystemExit('Local gateway secret key is missing')
PY
  ) || exit 2
  export GZ_JP_GATEWAY_SECRET
fi
RUN=/tmp/sensenran-run; mkdir -p $RUN
LOCK=$RUN/backend.lock.d
LOCKED=0
for i in $(seq 1 120); do mkdir "$LOCK" 2>/dev/null && { LOCKED=1; break; }; echo "waiting backend lock ($i)…"; sleep 5; done
[ "$LOCKED" = 1 ] || { echo "LOCK TIMEOUT"; exit 3; }
trap 'rmdir "$LOCK"' EXIT
MODS=${1:-ruoyi-modules/ruoyi-gz-common,ruoyi-modules/ruoyi-gz-bean,ruoyi-modules/ruoyi-gz-user,ruoyi-modules/ruoyi-gz-news,ruoyi-modules/ruoyi-gz-ord,ruoyi-modules/ruoyi-gz-gacha,ruoyi-modules/ruoyi-gz-coupon,ruoyi-modules/ruoyi-gz-recycle,ruoyi-modules/ruoyi-gz-jp}
cd $ROOT || exit 2
mvn -q clean install -DskipTests -pl "$MODS" -am || { echo "INSTALL FAILED"; exit 4; }
mvn -q clean -pl ruoyi-admin >/dev/null 2>&1   # 清掉 target/classes/db/migration 幽灵副本
LABEL=dev.sensenran-guzi.jp-snap.backend
if [ -x /bin/launchctl ]; then
  /bin/launchctl remove "$LABEL" >/dev/null 2>&1 || true
  for i in $(seq 1 30); do
    /bin/launchctl list "$LABEL" >/dev/null 2>&1 || break
    sleep 1
  done
fi
for p in $(lsof -tnP -iTCP:8080 -sTCP:LISTEN 2>/dev/null); do pkill -P $p 2>/dev/null; kill $p; done
pkill -f 'spring-boot:run -pl ruoyi-admin' 2>/dev/null
for i in $(seq 1 30); do lsof -tnP -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 1; done
LOG=$RUN/backend.log
if [ -x /bin/launchctl ]; then
  # launchd survives tool-session cleanup. Options stay in a private local file,
  # rather than exposing the HMAC secret in process arguments or a tracked file.
  /opt/homebrew/bin/python3.11 - "$RUN/backend-options.json" <<'PY'
import json, os, sys
keys = ('PATH', 'JAVA_HOME', 'MAVEN_OPTS', 'GZ_JP_GATEWAY_SECRET',
        'GZ_JP_GATEWAY_URL', 'GZ_LOCAL_SCHEDULER_ENABLED',
        'SPRING_APPLICATION_JSON', 'SPRING_PROFILES_ACTIVE',
        'SPRING_PROFILES_INCLUDE', 'NO_PROXY', 'no_proxy')
fd = os.open(sys.argv[1], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
os.fchmod(fd, 0o600)
with os.fdopen(fd, 'w') as out:
    json.dump({key: os.environ[key] for key in keys if key in os.environ}, out)
PY
  : > "$LOG"
  /bin/launchctl submit -l "$LABEL" -o "$LOG" -e "$LOG" -- \
    /opt/homebrew/bin/python3.11 "$SCRIPT_DIR/backend-start-local.py" "$ROOT" "$RUN/backend-options.json" || exit 5
else
  nohup mvn spring-boot:run -pl ruoyi-admin > "$LOG" 2>&1 < /dev/null &
  disown
fi
for i in $(seq 1 120); do
  grep -q '启动成功' $LOG && { echo "BACKEND UP (commit $(git rev-parse --short HEAD)$(git diff --quiet HEAD -- ruoyi-modules ruoyi-admin/src || echo +DIRTY-WORKTREE), branch $(git branch --show-current))"; grep -E 'Successfully (validated|applied)|Migrating schema' $LOG | tail -5; exit 0; }
  grep -qE 'APPLICATION FAILED|FlywayException|BUILD FAILURE' $LOG && { echo "BOOT FAILED"; grep -nE 'ERROR|Exception|FAILED' $LOG | head -30; exit 5; }
  sleep 3
done
echo "BOOT TIMEOUT"; tail -40 $LOG; exit 6
