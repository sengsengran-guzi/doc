import subprocess,re,json,hashlib,pathlib
log=pathlib.Path('/tmp/sensenran-run/backend.log').read_text()
pid=re.findall(r'Starting DromaraApplication using Java .*?PID (\d+)',log)[-1]
r=subprocess.run(['/usr/bin/jcmd',pid,'VM.system_properties'],capture_output=True,text=True);assert r.returncode==0,r.stderr
cp=next(x.split('=',1)[1] for x in r.stdout.splitlines() if x.startswith('java.class.path='))
jar=next(x for x in cp.replace(chr(92)+':',':').split(':') if '/ruoyi-gz-jp/' in x and x.endswith('.jar'))
sha=subprocess.check_output(['git','-C','code/main/RuoYi-Vue-Plus','rev-parse','HEAD'],text=True).strip()
out={'jvm_pid':pid,'jvm_self_reported_jp_classpath':jar,'loaded_jar_sha256':hashlib.sha256(pathlib.Path(jar).read_bytes()).hexdigest(),'source_commit':sha,'source_older_than_loaded_jar':all(p.stat().st_mtime<=pathlib.Path(jar).stat().st_mtime for p in pathlib.Path('code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/src/main/java').rglob('*.java')),'flyway_self_report':next(x for x in log.splitlines() if 'Successfully validated 187 migrations' in x)}
assert out['source_older_than_loaded_jar']
print(json.dumps(out,indent=2))
