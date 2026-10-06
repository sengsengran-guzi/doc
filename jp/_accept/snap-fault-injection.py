"""304 local real DB/HTTP concurrency acceptance. Replay + mock external dependencies only."""
import concurrent.futures, datetime, json, os, pathlib, subprocess, time, urllib.request
ROOT=pathlib.Path.cwd(); REPO=ROOT/'code/main/RuoYi-Vue-Plus'; CLIENT='mp-applet-gz-jp'; EXTERNAL='m99000000001';NOTE='GZ-SNAP-305 fault '+str(time.time_ns())
MYSQL=['/usr/local/bin/docker','exec','-i','sensenran-dev-mysql','mysql','-uroot','-proot','ry-vue','-N','--batch','--raw']
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

import hashlib,hmac,http.client,http.server,socket,socketserver,threading
GATEWAY=ROOT/'code/main/mercari-gateway'
options=ROOT/'doc/jp/_run/restart-backend.sh'
secret=''
for line in (GATEWAY/'.env').read_text().splitlines():
 key,sep,value=line.partition('=')
 if key.strip()=='GATEWAY_HMAC_SECRET':secret=value.strip().strip('"\'')
assert secret,'local gateway secret absent'
def gw(path,payload=None):
 body=b'' if payload is None else json.dumps(payload,separators=(',',':')).encode();method='GET' if payload is None else 'POST';ts=str(int(time.time()))
 sign=hmac.new(secret.encode(),(ts+'\n'+method+'\n'+path+'\n'+hashlib.sha256(body).hexdigest()).encode(),hashlib.sha256).hexdigest()
 req=urllib.request.Request('http://127.0.0.1:8712'+path,data=body if payload is not None else None,headers={'Content-Type':'application/json','X-GW-Ts':ts,'X-GW-Sign':sign},method=method)
 return json.load(urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=60))
# Each run has its own fake SQLite history. Do not reset the shared gateway ledger.
import tempfile
assert sql("SELECT COUNT(*) FROM gz_jp_snap_purchase WHERE tenant_id='1001' AND purchase_status IN ('queued','executing','unknown')")=='0','another active task exists'
fake_dir=pathlib.Path(tempfile.mkdtemp(prefix='snap305-fake-',dir='/tmp'))
fake_env=os.environ.copy();fake_env.update({'GATEWAY_DRIVER':'fake','GATEWAY_READ_SOURCE':'replay','GATEWAY_HMAC_SECRET':secret,'GATEWAY_ACCOUNTS':'acc01,acc02','GATEWAY_DB_PATH':str(fake_dir/'gateway.db'),'GATEWAY_REPLAY_DIR':str(GATEWAY/'fixtures/replay'),'GATEWAY_PROFILE_DIR':str(fake_dir/'profiles'),'GATEWAY_FAKE_TIMEOUT_SECONDS':'50'})
fake_log=open(fake_dir/'gateway.log','w')
fake_process=subprocess.Popen([str(GATEWAY/'.venv/bin/python'),'-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port','8712'],cwd=GATEWAY,env=fake_env,stdout=fake_log,stderr=subprocess.STDOUT)
for attempt in range(30):
 try:
  assert gw('/v1/health')['driver']=='fake';break
 except (OSError,urllib.error.URLError):time.sleep(.5)
else:
 fake_process.terminate();raise AssertionError('isolated fake gateway failed; see '+str(fake_dir/'gateway.log'))
print('isolated fake+replay ready: '+str(fake_dir),flush=True)
# Intercept only local HTTP. Same signed path/body is forwarded unchanged to fake gateway.
faults={}; clicked=threading.Event()
class Proxy(http.server.BaseHTTPRequestHandler):
 def handle_call(self):
  body=self.rfile.read(int(self.headers.get('Content-Length','0')));order=json.loads(body).get('order_no') if self.path=='/v1/purchases' else None
  conn=http.client.HTTPConnection('127.0.0.1',8712,timeout=65)
  try:
   conn.request(self.command,self.path,body,{k:v for k,v in self.headers.items() if k.lower() not in ('host','connection')})
   resp=conn.getresponse();data=resp.read()
   if order and faults.get(order)=='disconnect':
    self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
   if order and faults.get(order)=='restart':
    clicked.set();time.sleep(120) # keep purchase HTTP in flight until shared restart kills JVM
   self.send_response(resp.status)
   self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  except (BrokenPipeError,ConnectionResetError):pass
  finally:conn.close()
 def do_GET(self):self.handle_call()
 def do_POST(self):self.handle_call()
 def log_message(self,*args):pass
class LocalServer(http.server.ThreadingHTTPServer):
 def server_bind(self):
  socketserver.TCPServer.server_bind(self);self.server_name='localhost';self.server_port=self.server_address[1]
proxy=LocalServer(('127.0.0.1',8711),Proxy);proxy.daemon_threads=True
threading.Thread(target=proxy.serve_forever,daemon=True).start()
env=os.environ.copy();env.update({'GZ_LOCAL_SCHEDULER_ENABLED':'true','GZ_JP_GATEWAY_URL':'http://127.0.0.1:8711'})
def restart(enabled=True):
 env['GZ_LOCAL_SCHEDULER_ENABLED']='true' if enabled else 'false'
 env['GZ_JP_GATEWAY_URL']='http://127.0.0.1:8711' if enabled else 'http://127.0.0.1:8700'
 subprocess.run(['/bin/bash',str(options),'ruoyi-modules/ruoyi-gz-jp,ruoyi-modules/ruoyi-gz-common'],env=env,check=True)
# The caller installs current source through shared restart before DATA; check both artifact and running JVM.
def fresh():
 jars=list((pathlib.Path.home()/'.m2/repository/org/dromara/ruoyi-gz-jp').glob('*/*.jar'));assert jars
 jar=max(jars,key=lambda p:p.stat().st_mtime)
 assert all(p.stat().st_mtime<=jar.stat().st_mtime for p in (REPO/'ruoyi-modules/ruoyi-gz-jp/src/main/java').rglob('*.java')),'stale source/jar'
 pid=subprocess.check_output(['/usr/sbin/lsof','-t','-iTCP:8080','-sTCP:LISTEN']).decode().strip()
 start=datetime.datetime.strptime(subprocess.check_output(['/bin/ps','-p',pid,'-o','lstart=']).decode().strip(),'%a %b %d %H:%M:%S %Y').timestamp()
 assert start>=jar.stat().st_mtime-2,'stale JVM'
 print('fresh: current JP jar and running JVM; fake gateway verified',flush=True)
config_keys=['gz.jp.snap.pricing','gz.jp.snap.filter','gz.jp.snap.gate','gz.jp.snap.auto']
configs=snapshot('sys_config',"tenant_id='1001' AND config_key IN ("+','.join(map(lit,config_keys))+')');assert len(configs)==4
old_accounts=snapshot('gz_jp_snap_account',"tenant_id='1001'")
externals=['m99000000001','m99000000003','m99000000004','m99000000005']
old_items=snapshot('gz_jp_snap_item',"tenant_id='1001' AND external_id IN ("+','.join(map(lit,externals))+')')
assert all(x['active_order_item_id'] is None for x in old_items),'fixture item already held'
REDIS=['/usr/local/bin/docker','exec','-i','sensenran-dev-redis','redis-cli','-a','ruoyi123','--no-auth-warning','--raw']
def redis(*args):return subprocess.check_output(REDIS+list(args))
def clear_configs():
 for key in ('1001:sys_config','1001:1001:sys_config'):
  redis('HDEL',key,*config_keys)
caches={}
for key in ('1001:sys_config','1001:1001:sys_config'):
 for field in config_keys:
  exists=redis('HEXISTS',key,field).strip()==b'1';caches[(key,field)]=(exists,redis('HGET',key,field)[:-1] if exists else b'')
old_users=snapshot('gz_user',"tenant_id='1001'");fx_id=99030500001;addr_id=99030500002;user_id=None;order_ids=[];row_ids=[];file_ids=[];created_account=False;token=None
try:
 values={'gz.jp.snap.pricing':{'markupRatio':0,'fixedFeeCent':1,'estShippingCent':1,'quoteTtlSec':600},'gz.jp.snap.filter':{'categoryWhitelist':['745','974','975','980'],'keywordBlacklist':[]},'gz.jp.snap.gate':{'blockKeywords':[],'proxyRefuseKeywords':[],'manualKeywords':[]},'gz.jp.snap.auto':{'enabled':True}}
 for key,value in values.items():sql('UPDATE sys_config SET config_value='+lit(value)+" WHERE tenant_id='1001' AND config_key="+lit(key))
 clear_configs()
 sql("UPDATE gz_jp_snap_account SET admin_enabled=0 WHERE tenant_id='1001'")
 if not any(x['account_code']=='acc01' for x in old_accounts):
  sql("INSERT INTO gz_jp_snap_account(tenant_id,account_code,nickname,admin_enabled,health_status,daily_limit,today_count,cooldown_sec,create_time,update_time) VALUES('1001','acc01','305 fake',1,'healthy',100,0,0,NOW(),NOW())");created_account=True
 sql("UPDATE gz_jp_snap_account SET admin_enabled=1,health_status='healthy',pause_reason=NULL,daily_limit=100,today_count=0,today_date=CURRENT_DATE,cooldown_sec=0,last_purchase_at=NULL WHERE tenant_id='1001' AND account_code='acc01'")
 restart();fresh()
 assert sql('SELECT COUNT(*) FROM gz_jp_fx_rate WHERE id='+str(fx_id))=='0'
 sql("INSERT INTO gz_jp_fx_rate(id,tenant_id,rate_per_100jpy,source,fetched_at,create_by,create_time) VALUES("+str(fx_id)+",'1001',4.8,'manual',NOW(),1,NOW())")
 login=request('/app/gz/common/auth/wx-login',{'code':'snap305fault','nickName':'305 local fake'});assert login['code']==200,login
 token=login['data']['token'];user_id=int(login['data']['userId'])
 sql("INSERT INTO gz_user_address(id,tenant_id,user_id,recipient_name,mobile,province,city,district,detail,is_default,create_by,create_time) VALUES("+str(addr_id)+",'1001',"+str(user_id)+",'305 fixture','13800000000','四川省','成都市','锦江区','305 local fake',0,1,NOW())")
 def wait(predicate,seconds=95):
  until=time.monotonic()+seconds
  while time.monotonic()<until:
   value=predicate()
   if value:return value
   time.sleep(1)
  raise AssertionError('timed out waiting for fake task')
 for index,scenario in enumerate(['success','timeout','disconnect','restart']):
  detail=request('/app/gz/jp/snap/item/'+externals[index]);assert detail['code']==200,detail
  q=detail['data']['price']['quoteId'];submitted=request('/app/gz/jp/snap/order/submit',{'quoteId':q,'addressId':str(addr_id),'ackNoCancel':True,'userNote':NOTE},token);assert submitted['code']==200,submitted
  data=submitted['data'];order_no=data['orderNo'];oid=int(data['orderId']);order_ids.append(oid)
  rid=int(sql('SELECT id FROM gz_jp_order_item WHERE order_id='+str(oid)));row_ids.append(rid)
  outcome='timeout' if scenario=='timeout' else 'success' if scenario=='success' else 'unknown'
  gw('/v1/_fake/script',{'order_no':order_no,'outcome':outcome,'landed':True})
  if scenario in ('disconnect','restart'):faults[order_no]=scenario
  cb=request('/app/gz/test/pay/simulate-callback?outTradeNo='+data['payParams']['outTradeNo'],{},token);assert cb['code']==200,cb
  def status():return sql('SELECT purchase_status FROM gz_jp_snap_purchase WHERE order_item_id='+str(rid))
  if scenario=='restart':
   assert clicked.wait(20),'restart did not reach fake click'
   assert status()=='executing','restart must interrupt executing task'
   print('restart: fake click=1, DB executing before shared restart',flush=True)
   restart();fresh()
   # Accelerate only this exact task age to exercise the 60s recovery boundary.
   sql("UPDATE gz_jp_snap_purchase SET executed_at=DATE_SUB(NOW(),INTERVAL 61 SECOND) WHERE order_item_id="+str(rid)+" AND purchase_status='executing'")
  if scenario!='success':
   wait(lambda:status()=='unknown')
   assert sql('SELECT COUNT(*) FROM gz_jp_refund WHERE order_item_id='+str(rid))=='0'
   sql("UPDATE gz_jp_snap_purchase SET next_action_at=NOW() WHERE order_item_id="+str(rid)+" AND purchase_status='unknown'")
  wait(lambda:status() in ('success','manual_pending'))
  ledger=gw('/v1/_fake/ledger?order_no='+order_no)['orders'];assert len(ledger)==1 and ledger[0]['click_count']==1,ledger
  assert sql('SELECT COUNT(*) FROM gz_jp_refund WHERE order_item_id='+str(rid))=='0'
  evidence_ids=sql('SELECT evidence_file_ids FROM gz_jp_snap_purchase WHERE order_item_id='+str(rid))
  if scenario=='success':assert evidence_ids and evidence_ids!='NULL','successful response evidence must persist'
  print(scenario+': order='+order_no+' clicks=1 status='+status()+' refunds=0 evidence='+evidence_ids,flush=True)
  if scenario=='success':
   seconds=int(sql('SELECT TIMESTAMPDIFF(SECOND,o.paid_time,p.result_at) FROM gz_jp_order o JOIN gz_jp_snap_purchase p ON p.order_no=o.order_no AND p.tenant_id=o.tenant_id WHERE o.id='+str(oid)));assert 0<=seconds<60,seconds
   print('fake success latency='+str(seconds)+'s (<60s)',flush=True)
finally:
 restart(False)
 # Wait for the image worker to settle, then remove exact fixture metadata and rows only.
 time.sleep(3)
 for rid in row_ids:
  raw=sql("SELECT JSON_UNQUOTE(JSON_EXTRACT(product_snapshot_json,'$.snap.mainImageId')) FROM gz_jp_order_item WHERE id="+str(rid))
  if raw and raw!='NULL':file_ids.append(int(raw))
  raw=sql('SELECT evidence_file_ids FROM gz_jp_snap_purchase WHERE order_item_id='+str(rid))
  if raw and raw!='NULL':file_ids.extend(int(x) for x in raw.split(','))
  sql("DELETE FROM gz_jp_snap_purchase WHERE tenant_id='1001' AND order_item_id="+str(rid))
 for oid in order_ids:
  pay_ids=sql("SELECT id FROM gz_pay_transaction WHERE tenant_id='1001' AND business_order_no=(SELECT order_no FROM gz_jp_order WHERE id="+str(oid)+')').splitlines()
  for pid in pay_ids:
   sql("DELETE FROM gz_pay_callback_log WHERE tenant_id='1001' AND out_trade_no=(SELECT out_trade_no FROM gz_pay_transaction WHERE id="+pid+')');sql("DELETE FROM gz_pay_transaction WHERE tenant_id='1001' AND id="+pid)
 for rid in row_ids:sql("DELETE FROM gz_jp_order_item WHERE tenant_id='1001' AND id="+str(rid))
 for oid in order_ids:sql("DELETE FROM gz_jp_order WHERE tenant_id='1001' AND id="+str(oid))
 for fid in file_ids:sql("DELETE FROM gz_file_object WHERE tenant_id='1001' AND id="+str(fid))
 sql("DELETE FROM gz_user_address WHERE tenant_id='1001' AND id="+str(addr_id));sql("DELETE FROM gz_jp_fx_rate WHERE tenant_id='1001' AND id="+str(fx_id))
 for ext in externals:
  originals=[x for x in old_items if x['external_id']==ext]
  if originals:restore('gz_jp_snap_item',originals)
  else:sql("DELETE FROM gz_jp_snap_item WHERE tenant_id='1001' AND external_id="+lit(ext))
 restore('gz_jp_snap_account',old_accounts)
 if created_account:sql("DELETE FROM gz_jp_snap_account WHERE tenant_id='1001' AND account_code='acc01'")
 if user_id:
  originals=[x for x in old_users if int(x['id'])==user_id]
  if originals:restore('gz_user',originals)
  else:sql("DELETE FROM gz_user WHERE tenant_id='1001' AND id="+str(user_id))
 restore('sys_config',configs);clear_configs()
 for (key,field),(exists,value) in caches.items():
  if exists:subprocess.run(REDIS+['-x','HSET',key,field],input=value,check=True,stdout=subprocess.DEVNULL)
 (fake_dir/'ledger.json').write_text(json.dumps(gw('/v1/_fake/ledger'),indent=2))
 proxy.shutdown();fake_process.terminate();fake_process.wait(timeout=10);fake_log.close()
 assert snapshot('sys_config',"tenant_id='1001' AND config_key IN ("+','.join(map(lit,config_keys))+')')==configs
 print('restored: scheduler=false, gateway=8700, exact configs/cache/accounts/fixture data; real Mercari=0',flush=True)
