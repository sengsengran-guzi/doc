"""Inspect actual container/image, independent SQLite connection, exact QA cleanup."""
import hashlib
import json
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]/'code/main/mercari-gateway'
def docker(*args):
    return subprocess.check_output(['docker',*args],cwd=ROOT,text=True)
def code(source):
    return docker('compose','exec','-T','gateway','python','-c',source)
runtime=json.loads(code("import json,os,hashlib,pathlib; fs=list(pathlib.Path('app').rglob('*.py'))+list(pathlib.Path('fixtures').rglob('*')); print(json.dumps({'mode':[os.getenv('GATEWAY_DRIVER'),os.getenv('GATEWAY_READ_SOURCE')],'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in fs if p.is_file()}}))"))
assert runtime['mode']==['fake','replay']
for p,h in runtime['hashes'].items():
    assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
print('PASS runtime fake/replay all source/fixtures identical:',len(runtime['hashes']))
print('source fingerprint',json.dumps({p:h for p,h in runtime['hashes'].items() if p in ['app/main.py','app/store.py','app/read_sources/live.py']}))
image=json.loads(docker('inspect','mercari-gateway-gateway-1'))[0]
build=json.loads(docker('image','inspect','mercari-gateway:local'))[0]
assert image['Image']==build['Id']
print('PASS running image equals current built image',image['Image'])
print('container',image['Id'],'started',image['State']['StartedAt'])
print('PASS independent SQLite connection data and exact cleanup')
print(code("""import sqlite3,json,os
c=sqlite3.connect(os.environ['GATEWAY_DB_PATH'])
orders=['QA-D8-r1-1','QA-D8-r1-2','QA-D8-r1-3']
rows=c.execute('SELECT order_no,click_count,call_count FROM fake_ledger WHERE order_no IN (?,?,?)',orders).fetchall()
assert len(rows)==3 and all(x[1:]==(1,1) for x in rows),rows
states=c.execute('SELECT order_no,state,result_json FROM idempotency WHERE order_no IN (?,?,?)',orders).fetchall()
assert len(states)==3 and all(x[1]=='done' and json.loads(x[2])['result']=='success' for x in states)
facts=c.execute('SELECT order_no,COUNT(*) FROM fake_purchase WHERE order_no IN (?,?,?) GROUP BY order_no',orders).fetchall()
assert len(facts)==3 and all(x[1]==1 for x in facts),facts
print(json.dumps({'ledger':rows,'idempotency_states':[(x[0],x[1]) for x in states],'facts':facts}))
for table in ['fake_purchase','fake_ledger','idempotency']:
 c.execute('DELETE FROM '+table+' WHERE order_no IN (?,?,?)',orders)
 assert c.execute('SELECT COUNT(*) FROM '+table+' WHERE order_no IN (?,?,?)',orders).fetchone()[0]==0
c.commit()
print('cleanup 3 precise QA order numbers, 9 rows; remaining 0')
"""))
logs=docker('compose','logs','--no-color','gateway')
settings={}
for line in (ROOT/'.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        k,v=line.split('=',1);settings[k.strip()]=v.strip().strip('"').strip("'")
assert settings['GATEWAY_HMAC_SECRET'] not in logs
assert 'X-GW-Sign:' not in logs and 'Authorization:' not in logs
assert 'gateway 0.1.0 up driver=fake read_source=replay' in logs
assert 'signature mismatch' in logs and 'timestamp outside allowed clock skew' in logs
print('PASS runtime startup/auth/purchase logs have no configured secret or credential headers')
Path(__file__).with_name('gateway-log-r1.txt').write_text(logs)
assert not any(e.startswith('GATEWAY_HMAC_SECRET=') for e in build['Config']['Env'])
assert code("from pathlib import Path; print(Path('/app/.env').exists())").strip()=='False'
print('PASS image has no baked secret env or .env file')
print('COUNTS artifact/persistence checks 7')
