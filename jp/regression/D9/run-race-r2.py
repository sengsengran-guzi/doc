import pathlib,subprocess,os
root=pathlib.Path.cwd();os.environ['PATH']='/opt/homebrew/bin:'+os.environ['PATH']
query="SELECT 'FX',COUNT(*) FROM gz_jp_fx_rate WHERE tenant_id='1001' AND id=99030400001 UNION ALL SELECT 'ADDR',COUNT(*) FROM gz_user_address WHERE tenant_id='1001' AND id=99030400002 UNION ALL SELECT 'ORDER',COUNT(*) FROM gz_jp_order WHERE tenant_id='1001' AND user_note LIKE 'GZ-SNAP-304 race %'; SELECT external_id,COALESCE(active_order_item_id,0) FROM gz_jp_snap_item WHERE tenant_id='1001' AND external_id='m99000000001';"
p=subprocess.run(['docker','exec','-i','sensenran-dev-mysql','mysql','-uroot','-proot','ry-vue','-N','--batch'],input=query,text=True,capture_output=True)
print('precheck exit=',p.returncode);print(p.stdout);assert p.returncode==0,p.stderr
counts={line.split('\t')[0]:line.split('\t')[1] for line in p.stdout.splitlines()}
assert all(counts.get(k)=='0' for k in ['FX','ADDR','ORDER']),counts
assert counts.get('m99000000001','0')=='0',counts
result=subprocess.run(['/opt/homebrew/bin/python3.11','doc/jp/_accept/snap-submit-race.py'],text=True,capture_output=True)
raw=p.stdout+'\n'+result.stdout+'\n'+result.stderr
(root/'doc/jp/regression/D9/race-r2.log').write_text(raw)
print(result.stdout);print(result.stderr);raise SystemExit(result.returncode)
