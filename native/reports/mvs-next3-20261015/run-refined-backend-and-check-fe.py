import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
b=Path(__file__).resolve().parent
while not (b/'sonatina-join-commit.json').exists(): time.sleep(5)
commits=json.loads((b/'sonatina-join-commit.json').read_text())
fe=b/'fe-ablation'
env={**os.environ,'TMPDIR':'/dev/shm/fevm-mvs-runs','RAYON_NUM_THREADS':'1','CARGO_BUILD_JOBS':'2','CARGO_TARGET_DIR':'/tmp/fevm-mvs-target-preserved-on-disk','CARGO_NET_GIT_FETCH_WITH_CLI':'true'}
count=int(env.get('GIT_CONFIG_COUNT','0'));env[f'GIT_CONFIG_KEY_{count}']=f'url.{(b/"sonatina").as_uri()}.insteadOf';env[f'GIT_CONFIG_VALUE_{count}']='https://github.com/fe-lang/sonatina';env['GIT_CONFIG_COUNT']=str(count+1)
previous='ca25abf9a96ce4d31da3923cc4a6dddc13be3c81'
records=[]
for name in ['join']:
 rev=commits[name]
 for file,expected in [('Cargo.toml',4),('Cargo.lock',12)]:
  p=fe/file;s=p.read_text();assert s.count(previous)==expected,(file,s.count(previous));p.write_text(s.replace(previous,rev))
 previous=rev
 out=b/f'ablation-{name}';(out/'bin').mkdir(parents=True)
 started=time.perf_counter()
 with (out/'build.jsonl').open('wb') as log,(out/'build.log').open('wb') as errors:
  status=subprocess.run(['cargo','+1.99.0','build','--release','--locked','-p','fe','--features','cranelift','--message-format=json'],cwd=fe,env=env,stdout=log,stderr=errors).returncode
 print(f'{name} build: {status}',flush=True)
 if status: raise SystemExit(status)
 artifact=next(x for x in map(json.loads,(out/'build.jsonl').read_text().splitlines()) if x.get('reason')=='compiler-artifact' and x['target']['name']=='fe' and x.get('executable'))
 compiler=out/'bin/fe';shutil.copy2(artifact['executable'],compiler)
 record={'complete':True,'experimental':True,'source_fe_base':'d7fdfbb73956b2f3d41e7f4b8101a5a49de46509','sonatina_revision':rev,'seconds':time.perf_counter()-started,'compiler':str(compiler),'compiler_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(),'cargo_lock_sha256':hashlib.sha256((fe/'Cargo.lock').read_bytes()).hexdigest()}
 (out/'build.json').write_text(json.dumps(record,indent=2)+'\n')
 with (out/'fe-source.patch').open('wb') as patch: subprocess.run(['git','diff','HEAD'],cwd=fe,stdout=patch,check=True)
 subprocess.run(['python3',str(b/'workspace-report.py'),f'{name}-O1',str(compiler)],check=True)
 records.append(record);(b/'join-ablation-progress.json').write_text(json.dumps(records,indent=2)+'\n')
print('Refined backend ablation complete.',flush=True)

main_fe=b/'fe'
for file,expected in [('Cargo.toml',4),('Cargo.lock',12)]:
 p=main_fe/file;text=p.read_text();old='ca25abf9a96ce4d31da3923cc4a6dddc13be3c81';assert text.count(old)==expected;p.write_text(text.replace(old,rev))
lock=hashlib.sha256((main_fe/'Cargo.lock').read_bytes()).hexdigest()
(b/'fe-pin-update.json').write_text(json.dumps({'sonatina_revision':rev,'cargo_lock_sha256':lock},indent=2)+'\n')
print('Checking final Fe source against backend',rev,flush=True)
raise SystemExit(subprocess.run(['python3',str(b/'check-fe.py')]).returncode)
