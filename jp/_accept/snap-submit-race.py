"""304 local real DB/HTTP concurrency acceptance. Replay + mock external dependencies only."""
import concurrent.futures, datetime, json, os, pathlib, subprocess, time, urllib.request
ROOT=pathlib.Path.cwd(); REPO=ROOT/'code/main/RuoYi-Vue-Plus'; CLIENT='mp-applet-gz-jp'; EXTERNAL='m99000000001';NOTE='GZ-SNAP-304 race '+str(time.time_ns())
MYSQL=['docker','exec','-i','sensenran-dev-mysql','mysql','-uroot','-proot','ry-vue','-N','--batch','--raw']
def sql(query):
 result=subprocess.run(MYSQL,input=query.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if result.returncode:
  raise RuntimeError('local MySQL SQL failed: '+query+'\n'+result.stderr.decode(errors='replace'))
 return result.stdout.decode().strip()
def lit(value):
 if value is None:return 'NULL'
 if isinstance(value,(dict,list)):value=json.dumps(value,ensure_ascii=False,separators=(',',':'))
 return "CONVERT(0x"+str(value).encode().hex()+" USING utf8mb4) COLLATE utf8mb4_bin" if str(value) else "''"
def request(path,payload=None,token=None):
 headers={'clientid':CLIENT,'Content-Type':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 req=urllib.request.Request('http://127.0.0.1:8080'+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers)
 return json.load(urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=60))
def snapshot(table,where):
 cols=[line.split('\t')[0] for line in sql('SHOW COLUMNS FROM '+table).splitlines()]
 expression=','.join(lit(c)+',`'+c+'`' for c in cols)
 raw=sql('SELECT JSON_OBJECT('+expression+') FROM '+table+' WHERE '+where)
 return [json.loads(line) for line in raw.splitlines()] if raw else []
def restore(table,rows):
 for row in rows:
  sql('UPDATE '+table+' SET '+','.join('`'+k+'`='+lit(v) for k,v in row.items())+' WHERE '+('config_id' if table=='sys_config' else 'id')+'='+str(row.get('config_id',row.get('id'))))
# Verify installed jar and the running JVM both postdate source/commit; fail before creating data.
jars=list((pathlib.Path.home()/'.m2/repository/org/dromara/ruoyi-gz-jp').glob('*/*.jar'))
assert jars,'stale: missing installed jp jar'
jar=max(jars,key=lambda p:p.stat().st_mtime)
assert all(p.stat().st_mtime<=jar.stat().st_mtime for p in (REPO/'ruoyi-modules/ruoyi-gz-jp/src/main/java').rglob('*.java')),'stale: source newer than installed jar'
pids=subprocess.check_output(['lsof','-t','-iTCP:8080','-sTCP:LISTEN']).decode().split()
assert len(pids)==1,'expected one local backend JVM'
started=subprocess.check_output(['ps','-p',pids[0],'-o','lstart=']).decode().strip()
start=datetime.datetime.strptime(started,'%a %b %d %H:%M:%S %Y').timestamp()
commit_time=int(subprocess.check_output(['git','-C',str(REPO),'log','-1','--format=%ct','--','ruoyi-modules/ruoyi-gz-jp/src/main','ruoyi-admin/src']).decode())
assert start>=max(commit_time,jar.stat().st_mtime)-2,'stale: backend was started before current commit/jar'
assert request('/app/gz/jp/snap/hot-terms')['code']==200,'backend unavailable'
print('fresh: installed JP jar and JVM postdate production-path commit; test-only HEAD may differ; local replay only')
config_keys=['gz.jp.snap.pricing','gz.jp.snap.filter','gz.jp.snap.gate']
configs=snapshot('sys_config','tenant_id=\'1001\' AND config_key IN ('+','.join(map(lit,config_keys))+')')
assert len(configs)==3,'required config seeds missing'
old_items=snapshot('gz_jp_snap_item',"tenant_id='1001' AND external_id="+lit(EXTERNAL))
assert not old_items or old_items[0]['active_order_item_id'] is None,'fixture item occupied; do not overwrite another test'
# Both cache namespaces are explicit; preserve exact Redis binary dump and TTL in Python base64 via redis-cli --raw.
# Redisson RMap entries are backed by a hash; save selected field bytes and restore only those fields.
REDIS=['docker','exec','-i','sensenran-dev-redis','redis-cli','-a','ruoyi123','--no-auth-warning','--raw']
def redis(*args):return subprocess.check_output(REDIS+list(args))
caches={}
for key in ('1001:sys_config','1001:1001:sys_config'):
 for field in config_keys:
  exists=redis('HEXISTS',key,field).strip()==b'1'
  caches[(key,field)]=(exists,redis('HGET',key,field)[:-1] if exists else b'')
  redis('HDEL',key,field)
old_users=snapshot('gz_user',"tenant_id='1001'")
fx_id=99030400001;addr_id=99030400002;order_ids=[];row_ids=[];pay_ids=[];file_ids=[];token=None;user_id=None
try:
 values={'gz.jp.snap.pricing':{'markupRatio':0,'fixedFeeCent':1,'estShippingCent':1,'quoteTtlSec':600},'gz.jp.snap.filter':{'categoryWhitelist':['745','975','980'],'keywordBlacklist':[]},'gz.jp.snap.gate':{'blockKeywords':['専用'],'proxyRefuseKeywords':['代行不可'],'manualKeywords':['コメントして']}}
 for key,value in values.items():sql('UPDATE sys_config SET config_value='+lit(json.dumps(value,ensure_ascii=False))+' WHERE tenant_id=\'1001\' AND config_key='+lit(key))
 assert sql('SELECT COUNT(*) FROM gz_jp_fx_rate WHERE id='+str(fx_id))=='0','reserved FX id collision'
 sql("INSERT INTO gz_jp_fx_rate(id,tenant_id,rate_per_100jpy,source,fetched_at,create_by,create_time) VALUES("+str(fx_id)+",'1001',4.8,'manual',NOW(),1,NOW())")
 login=request('/app/gz/common/auth/wx-login',{'code':'snap304race','nickName':'304 local acceptance'})
 assert login['code']==200,login
 token=login['data']['token'];user_id=int(login['data']['userId'])
 assert sql('SELECT COUNT(*) FROM gz_user_address WHERE id='+str(addr_id))=='0','reserved address collision'
 sql("INSERT INTO gz_user_address(id,tenant_id,user_id,recipient_name,mobile,province,city,district,detail,is_default,create_by,create_time) VALUES("+str(addr_id)+",'1001',"+str(user_id)+",'304 fixture','13800000000','四川省','成都市','锦江区','本地回放验收地址',0,1,NOW())")
 detail=request('/app/gz/jp/snap/item/'+EXTERNAL)
 assert detail['code']==200 and detail['data']['price'] is not None,detail
 quote=detail['data']['price']['quoteId'];payload={'quoteId':quote,'addressId':str(addr_id),'ackNoCancel':True,'userNote':NOTE}
 with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
  replies=list(pool.map(lambda _:request('/app/gz/jp/snap/order/submit',payload,token),range(10)))
 successful=[r['data'] for r in replies if r['code']==200]
 # Record all created fixture orders even if an assertion fails, so cleanup remains exact.
 raw=sql("SELECT o.id,i.id FROM gz_jp_order o JOIN gz_jp_order_item i ON i.order_id=o.id AND i.tenant_id=o.tenant_id JOIN gz_jp_snap_item s ON s.id=i.snap_item_id AND s.tenant_id=i.tenant_id WHERE o.tenant_id='1001' AND o.user_note="+lit(NOTE)+" AND o.user_id="+str(user_id)+" AND s.external_id="+lit(EXTERNAL))
 for line in raw.splitlines():
  oid,rid=map(int,line.split('\t'));order_ids.append(oid);row_ids.append(rid)
 assert successful,replies
 distinct={r['orderNo'] for r in successful};assert len(distinct)==1,replies
 assert all(r['code'] in (200,4127) for r in replies),replies
 assert len(order_ids)==1 and len(row_ids)==1,(order_ids,row_ids)
 active=sql("SELECT COUNT(*) FROM gz_jp_order_item i JOIN gz_jp_order o ON o.id=i.order_id AND o.tenant_id=i.tenant_id WHERE i.tenant_id='1001' AND i.snap_item_id="+str(int(sql("SELECT id FROM gz_jp_snap_item WHERE tenant_id='1001' AND external_id="+lit(EXTERNAL))))+" AND i.source='snap' AND i.del_flag='0' AND o.del_flag='0' AND o.business_status IN ('created','paid')")
 assert active=='1',active
 terms=json.loads(sql('SELECT product_snapshot_json FROM gz_jp_order_item WHERE id='+str(row_ids[0])))['snap']
 assert terms['priceJpy']==801 and float(terms['ratePer100Jpy'])==4.8 and terms['ackNoCancel'] is True,terms
 assert terms['mainImageUrl'].startswith('https://static.mercdn.net/'),terms
 assert len({r['payParams']['outTradeNo'] for r in successful})==1,'pending prepay must be reused'
 print('race: requests=10 successful='+str(len(successful))+' distinctOrderNo=1 DBactiveRows=1 prepayTransactions=1')
 callback_path='/app/gz/test/pay/simulate-callback?outTradeNo='+successful[0]['payParams']['outTradeNo']
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  paid_future=pool.submit(request,callback_path,{},token)
  submit_future=pool.submit(request,'/app/gz/jp/snap/order/submit',payload,token)
  assert paid_future.result()['code']==200
  assert submit_future.result()['code'] in (200,4128),submit_future.result()
 assert request(callback_path,{},token)['code']==200
 print('payment/owner-resubmit race: both returned permitted business states, no lock inversion/500')
 tasks=sql('SELECT COUNT(*),MIN(purchase_status),MIN(mode) FROM gz_jp_snap_purchase WHERE tenant_id=\'1001\' AND order_item_id='+str(row_ids[0])).split('\t')
 assert tasks==['1','manual_pending','manual'],tasks
 print('paid: callbacks=2 taskCount=1 mode=manual status=manual_pending (original auto disabled)')
 read=request('/app/gz/jp/order/'+str(order_ids[0]),token=token)
 assert read['code']==200 and 'ratePer100' not in json.dumps(read) and 'markupRatio' not in json.dumps(read) and 'static.mercdn.net' not in json.dumps(read)
 print('mp order read: server-only FX/markup absent; title/snapshot read succeeds')
finally:
 if user_id is not None:
  remaining=sql("SELECT o.id,i.id FROM gz_jp_order o JOIN gz_jp_order_item i ON i.order_id=o.id AND i.tenant_id=o.tenant_id JOIN gz_jp_snap_item s ON s.id=i.snap_item_id AND s.tenant_id=i.tenant_id WHERE o.tenant_id='1001' AND o.user_note="+lit(NOTE)+" AND o.user_id="+str(user_id)+" AND s.external_id="+lit(EXTERNAL))
  order_ids=[];row_ids=[]
  for line in remaining.splitlines():
   oid,rid=map(int,line.split('\t'));order_ids.append(oid);row_ids.append(rid)
 # Wait boundedly for the after-commit image worker before deleting its exact uploaded object metadata.
 if row_ids:
  for _ in range(60):
   image=sql("SELECT JSON_UNQUOTE(JSON_EXTRACT(product_snapshot_json,'$.snap.mainImageId')) FROM gz_jp_order_item WHERE id="+str(row_ids[0]))
   if image and image!='NULL':file_ids.append(int(image));break
   time.sleep(.5)
 for oid in order_ids:
  pay_ids.extend(int(x) for x in sql("SELECT id FROM gz_pay_transaction WHERE tenant_id='1001' AND business_order_no=(SELECT order_no FROM gz_jp_order WHERE id="+str(oid)+")").splitlines())
 for rid in row_ids:sql("DELETE FROM gz_jp_snap_purchase WHERE tenant_id='1001' AND order_item_id="+str(rid))
 for pid in pay_ids:
  # Callback log is keyed by out_trade_no, not business order ID.
  sql("DELETE FROM gz_pay_callback_log WHERE tenant_id='1001' AND out_trade_no=(SELECT out_trade_no FROM gz_pay_transaction WHERE id="+str(pid)+")")
  sql("DELETE FROM gz_pay_transaction WHERE tenant_id='1001' AND id="+str(pid))
 for rid in row_ids:sql("DELETE FROM gz_jp_order_item WHERE tenant_id='1001' AND id="+str(rid))
 for oid in order_ids:sql("DELETE FROM gz_jp_order WHERE tenant_id='1001' AND id="+str(oid))
 for fid in file_ids:sql("DELETE FROM gz_file_object WHERE tenant_id='1001' AND id="+str(fid))
 sql("DELETE FROM gz_user_address WHERE tenant_id='1001' AND id="+str(addr_id))
 sql("DELETE FROM gz_jp_fx_rate WHERE tenant_id='1001' AND id="+str(fx_id))
 if old_items:restore('gz_jp_snap_item',old_items)
 else:sql("DELETE FROM gz_jp_snap_item WHERE tenant_id='1001' AND external_id="+lit(EXTERNAL))
 if user_id is not None:
  originals=[row for row in old_users if int(row['id'])==user_id]
  if originals:restore('gz_user',originals)
  else:sql("DELETE FROM gz_user WHERE tenant_id='1001' AND id="+str(user_id))
 restore('sys_config',configs)
 for (key,field),(exists,value) in caches.items():
  redis('HDEL',key,field)
  if exists:subprocess.run(REDIS+['-x','HSET',key,field],input=value,check=True,stdout=subprocess.DEVNULL)
 assert snapshot('sys_config','tenant_id=\'1001\' AND config_key IN ('+','.join(map(lit,config_keys))+')')==configs,'config restoration mismatch'
 print('restored: exact config rows/cache fields, FX/address/orders/tasks and snap item; real Mercari calls=0')
