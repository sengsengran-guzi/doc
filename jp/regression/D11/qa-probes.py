import json,urllib.request,subprocess,threading,concurrent.futures,time,hashlib,pathlib,os
root=pathlib.Path(__file__).resolve().parents[4]
client='e5cd7e4891bf95d1d19206ce24a7b32e'
count=0
def check(condition,label):
 global count
 count+=1
 assert condition,label
 print('PASS',count,label,flush=True)
def sql(q):
 return subprocess.check_output(['/usr/local/bin/docker','exec','-i','sensenran-dev-mysql','mysql','-uroot','-proot','ry-vue','-N','--batch','--raw'],input=q,text=True,stderr=subprocess.DEVNULL).strip()
def api(path,body=None,token='',method=None):
 req=urllib.request.Request('http://127.0.0.1:8080'+path,data=None if body is None else json.dumps(body).encode(),headers={'clientid':client,'Content-Type':'application/json','Connection':'close',**({'Authorization':'Bearer '+token} if token else {})},method=method or ('GET' if body is None else 'POST'))
 return json.load(urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=30))
def login(name,pwd):
 r=api('/auth/login',dict(tenantId='1001',username=name,password=pwd,clientId=client,grantType='password'))
 check(r['code']==200,'login '+name)
 return r['data']['access_token']
owner=login('gz_owner','gz_owner123!');staff=login('gz_staff_chengdu','gz_staff123!')
menus=sql("SELECT menu_id,parent_id,path,component,perms,visible FROM sys_menu WHERE menu_id BETWEEN 14040 AND 14089 ORDER BY menu_id")
print('MENU ANCHOR',menus)
check(sql("SELECT COUNT(*) FROM sys_menu m WHERE m.menu_id BETWEEN 14040 AND 14089 AND ((m.menu_type IN ('M','C') AND COALESCE(m.path,'')='') OR (m.menu_type='C' AND COALESCE(m.component,'')='') OR (m.parent_id<>0 AND NOT EXISTS(SELECT 1 FROM sys_menu p WHERE p.menu_id=m.parent_id)))")=='0','menu nonempty/path/component/parent')
for mid in [14050,14060,14070,14080]:check(sql(f"SELECT COUNT(*) FROM sys_menu WHERE menu_id={mid} AND parent_id=14040 AND menu_type='C'")=='1',f'menu {mid} parent')
r=api('/system/menu/getRouters',token=owner);check(r['code']==200,'owner routers code')
for page in ['purchase','account','config','term']:check('gz-jp/snap/'+page+'/index' in json.dumps(r),'router '+page)
for path,body,method in [('/account/list',None,'GET'),('/account/auto-switch/resume',{'confirmed':True},'POST'),('/config/trade',None,'GET'),('/config/trade',{'rateDeadlineHours':24,'patrolMinutes':20},'PUT'),('/fx',{'ratePer100jpy':4},'POST')]:
 r=api('/system/gz/jp/snap'+path,body,staff,method);check(r['code']==403,'staff forbidden '+method+path)
word='QA-D11-RACE-'+str(time.time_ns());prefix='/system/gz/jp/snap/term'
check(sql("SELECT COUNT(*) FROM gz_jp_snap_term WHERE zh_term='"+word+"'")=='0','unique word absent')
snapshot=sql("SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT('id',id,'zh',HEX(zh_term),'ja',HEX(ja_term),'enabled',enabled,'del',del_flag,'updated',update_time)),JSON_ARRAY()) FROM (SELECT * FROM gz_jp_snap_term ORDER BY id)t")
barrier=threading.Barrier(2);ids=[]
def add(n):
 barrier.wait()
 return api(prefix,dict(zhTerm=word,jaTerm='同時'+str(n),termType='ip',enabled=True,sortNo=411),owner)
try:
 with concurrent.futures.ThreadPoolExecutor(2) as pool: results=list(pool.map(add,[1,2]))
 print('CONCURRENT TWO CONNECTION RESULTS',json.dumps(results,ensure_ascii=False))
 ids=[str(r['data']) for r in results if r['code']==200]
 check(len(ids)==1,'exactly one successful add; one duplicate rejected')
 check(any('中文词已存在' in r.get('msg','') for r in results if r['code']!=200),'loser friendly duplicate')
 check(sql("SELECT COUNT(*) FROM gz_jp_snap_term WHERE tenant_id='1001' AND zh_term='"+word+"' AND del_flag='0'")=='1','DB exactly one dictionary side effect')
 r=api(prefix+'/normalize',{'q':word},owner);check(r['code']==200 and r['data']['query'].startswith('同時'),'normalize sees committed winner immediately')
finally:
 for rowid in ids:
  r=api(prefix+'/'+rowid,token=owner,method='DELETE');check(r['code']==200,'API remove own term')
  sql(f"DELETE FROM gz_jp_snap_term WHERE id={rowid} AND zh_term='{word}' AND del_flag='1' AND tenant_id='1001'")
 check(sql("SELECT COUNT(*) FROM gz_jp_snap_term WHERE zh_term='"+word+"'")=='0','own fixture absent after cleanup')
 check(sql("SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT('id',id,'zh',HEX(zh_term),'ja',HEX(ja_term),'enabled',enabled,'del',del_flag,'updated',update_time)),JSON_ARRAY()) FROM (SELECT * FROM gz_jp_snap_term ORDER BY id)t")==snapshot,'existing dictionary exact readback unchanged')
print('TOTAL_ASSERTIONS',count)
