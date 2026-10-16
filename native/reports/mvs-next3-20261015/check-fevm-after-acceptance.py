import json,os,subprocess,time
from pathlib import Path
b=Path(__file__).resolve().parent
root=Path('/home/sean/code/fevm')
while True:
 try:
  acceptance=json.loads((b/'acceptance/acceptance.json').read_text())
  if acceptance['complete']:break
 except (OSError,ValueError):pass
 time.sleep(5)
env={**os.environ,'TMPDIR':'/dev/shm/fevm-mvs-runs','RAYON_NUM_THREADS':'1','CARGO_BUILD_JOBS':'2'}
commands=[('python',[ 'python3','-m','unittest','discover','-s','native/differential','-p','test_*.py'],root),('reference-format',['cargo','+nightly','fmt','--all'],root/'native/differential/reference'),('reference-nextest',['cargo','+1.99.0','nextest','r','--release','--no-fail-fast','--locked','--all-features'],root/'native/differential/reference'),('reference-clippy',['cargo','+1.99.0','clippy','--release','--locked','--all-features','--all-targets','--','-D','warnings'],root/'native/differential/reference'),('reference-format-check',['cargo','+nightly','fmt','--all','--','--check'],root/'native/differential/reference')]
record={'complete':False,'checks':[]}
for name,cmd,cwd in commands:
 start=time.perf_counter()
 with (b/f'fevm-{name}.log').open('wb') as log:status=subprocess.run(cmd,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
 record['checks'].append({'name':name,'command':cmd,'status':status,'seconds':time.perf_counter()-start})
 (b/'fevm-checks.json').write_text(json.dumps(record,indent=2)+'\n')
 print(name,status,flush=True)
 if status:raise SystemExit(status)
record['complete']=True;(b/'fevm-checks.json').write_text(json.dumps(record,indent=2)+'\n')
