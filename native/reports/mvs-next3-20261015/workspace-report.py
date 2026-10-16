import hashlib,json,os,subprocess,time,sys
from pathlib import Path
b=Path(__file__).resolve().parent
name,compiler=sys.argv[1:]
command=[compiler,'test','--backend','native','--jobs','1','-O','1','--report','--report-out',str(b/f'{name}-native-report.tar.gz'),'/home/sean/code/fevm']
env={**os.environ,'TMPDIR':'/dev/shm/fevm-mvs-runs','RAYON_NUM_THREADS':'1','CARGO_BUILD_JOBS':'2','FE_REMOTE_CACHE_DIR':str(b/'ingot-cache')}
start=time.perf_counter()
with (b/f'{name}.log').open('wb') as log:
 status=subprocess.run(['/usr/bin/time','-v',*command],cwd='/dev/shm/fevm-mvs-runs',env=env,stdout=log,stderr=subprocess.STDOUT).returncode
record={'status':status,'seconds':time.perf_counter()-start,'command':command,'compiler_sha256':hashlib.sha256(Path(compiler).read_bytes()).hexdigest(),'scope':'Full one-thread O1 workspace with reports enabled on both sides; report serialization included'}
(b/f'{name}.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
raise SystemExit(status)
