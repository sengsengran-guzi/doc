"""Restore verified FULL-binlog snapshots after all D11 QA writers have stopped."""
import json
import subprocess
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent
SNAPSHOTS = json.loads((BASE / 'pre-qa-config-binlog.json').read_text())
CLIENT = 'e5cd7e4891bf95d1d19206ce24a7b32e'


def sql(query):
    return subprocess.check_output(
        ['/usr/local/bin/docker', 'exec', '-i', 'sensenran-dev-mysql', 'mysql',
         '-uroot', '-proot', 'ry-vue', '-N', '--batch', '--raw'],
        input=query, text=True, stderr=subprocess.DEVNULL).strip()


def literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, int):
        return str(value)
    return '(CONVERT(0x' + value.encode().hex() + ' USING utf8mb4) COLLATE utf8mb4_bin)'


def current(row):
    return json.loads(sql(
        "SELECT JSON_OBJECT('value',config_value,'by',update_by,'time',"
        "CAST(update_time AS CHAR)) FROM sys_config WHERE config_id="
        + str(row['config_id']) + " AND tenant_id='1001' AND config_key="
        + literal(row['config_key'])))


statements = ['START TRANSACTION;']
for key, entry in SNAPSHOTS.items():
    row = entry['before']
    assert row['tenant_id'] == '1001' and row['config_key'] == key
    assert current(row)['value'] == row['config_value'], key + ': unexpected value'
    statements.append(
        'UPDATE sys_config SET config_value=' + literal(row['config_value'])
        + ',update_by=' + literal(row['update_by'])
        + ',update_time=' + literal(row['update_time'])
        + ' WHERE config_id=' + str(row['config_id'])
        + " AND tenant_id='1001' AND config_key=" + literal(key)
        + ' AND BINARY config_value=BINARY ' + literal(row['config_value']) + ';')
statements.append('COMMIT;')
sql('\n'.join(statements))
for entry in SNAPSHOTS.values():
    row = entry['before']
    assert current(row) == {'value': row['config_value'], 'by': row['update_by'],
                            'time': row['update_time']}, row['config_key']

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def api(path, token='', method='GET', body=None):
    headers = {'clientid': CLIENT, 'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request(
        'http://127.0.0.1:8080' + path, headers=headers, method=method,
        data=None if body is None else json.dumps(body).encode())
    with opener.open(request, timeout=30) as response:
        result = json.load(response)
    assert result['code'] == 200, path + ': ' + str(result['code'])
    return result


login = api('/auth/login', method='POST', body={
    'tenantId': '1001', 'username': 'admin', 'password': 'admin123',
    'clientId': CLIENT, 'grantType': 'password'})
token = login['data']['access_token']
try:
    api('/system/tenant/dynamic/1001', token)
    api('/system/config/refreshCache', token, method='DELETE')
    for key, entry in SNAPSHOTS.items():
        assert api('/system/config/configKey/' + key, token)['data'] == entry['before']['config_value'], key
finally:
    api('/system/tenant/dynamic/clear', token)

result = {'restoredKeys': list(SNAPSHOTS), 'exactDbValueAndAuditReadbacks': 5,
          'frameworkCacheReadbacks': 5, 'source': 'FULL binlog pre-QA before-image',
          'otherColumnsWritten': False}
(BASE / 'config-restoration.json').write_text(json.dumps(result, indent=2) + '\n')
print('PASS: five exact pre-QA values/update_by/update_time; five framework cache readbacks; dynamic tenant cleared')
