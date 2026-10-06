import os,sys,json,subprocess,pathlib,hashlib,tempfile
ROOT=pathlib.Path('/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi');MP=ROOT/'code/main/miniapp-jp';D='/usr/local/bin/docker'
def sql(s):
 p=subprocess.run([D,'exec','sensenran-dev-mysql','mysql','-uroot','-proot','-N','--batch','--raw','--default-character-set=utf8mb4','ry-vue','-e',s],capture_output=True,text=True)
 if p.returncode:raise RuntimeError('QA SQL failed; query withheld')
 return p.stdout.strip()
def snap(table,where,key='id'):
 cols=[x.split('\t')[0] for x in sql('SHOW COLUMNS FROM '+table).splitlines()];q='SELECT '+','.join("IF("+c+" IS NULL,'NULL',HEX(CAST("+c+" AS CHAR)))" for c in cols)+' FROM '+table+' WHERE '+where+' ORDER BY '+key
 return dict(table=table,cols=cols,where=where,key=key,q=q,raw=sql(q))
def restore(s):
 for row in s['raw'].splitlines():
  values=[('NULL' if v=='NULL' else "''" if v=='' else 'CONVERT(0x'+v+' USING utf8mb4)') for v in row.split('\t')];idx=s['cols'].index(s['key'])
  sql('UPDATE '+s['table']+' SET '+','.join(c+'='+v for c,v in zip(s['cols'],values))+' WHERE '+s['where']+' AND '+s['key']+'='+values[idx])
base=[snap('sys_config',"tenant_id='1001' AND config_key IN ('gz.jp.snap.pricing','gz.jp.snap.filter','gz.jp.snap.gate','gz.jp.snap.trade','gz.jp.snap.auto')",'config_id'),snap('gz_jp_snap_item',"tenant_id='1001'"),snap('gz_user',"tenant_id='1001' AND id=14"),snap('gz_user_address',"tenant_id='1001' AND user_id=14"),snap('gz_jp_cart_item',"tenant_id='1001' AND user_id=14"),snap('gz_jp_fx_rate',"tenant_id='1001'"),snap('gz_jp_snap_account',"tenant_id='1001'")]
fd,path=tempfile.mkstemp(prefix='d12-qa-private-',suffix='.json');os.fchmod(fd,0o600)
with os.fdopen(fd,'w') as f:json.dump(base,f)
env=dict(os.environ,NO_PROXY='localhost,127.0.0.1',CHOKIDAR_USEPOLLING='true');env.pop('MP_SNAP504_OUTCOMES',None)
env['PATH']='/Users/wkui/.nvm/versions/node/v24.11.1/bin:/opt/homebrew/bin:'+env.get('PATH','');env['MP_E2E_TIMEOUT_MS']='900000'
result=None;errors=[]
try:
 result=subprocess.run(['node','test/e2e/run.mjs',sys.argv[1],'--no-auto-build'],cwd=MP,env=env)
finally:
 # Inner reviewed fixture guards remove exact owned order/pay/callback/refund/file IDs,
 # restore customer rows, and invalidate config caches through the admin APIs.
 # Outer fallback restores every baseline row, even if a flow throws.
 for s in base:
  try:
   before_restore=sql(s['q'])==s['raw']
   restore(s)
   assert sql(s['q'])==s['raw'],s['table']+' exact rows/audit mismatch'
   print('QA OUTER EXACT',s['table'],'innerAlreadyExact='+str(before_restore),hashlib.sha256(s['raw'].encode()).hexdigest(),flush=True)
  except Exception as e:errors.append(str(e))
 if errors:raise RuntimeError('Recovery errors; mode600 snapshot retained '+path+'; '+';'.join(errors))
 os.unlink(path)
sys.exit(result.returncode if result else 1)
