import hashlib,json,os,subprocess
from pathlib import Path
b=Path(__file__).resolve().parent
root=Path('/home/sean/code/fevm')
env={**os.environ,'TMPDIR':'/dev/shm/fevm-mvs-runs','RAYON_NUM_THREADS':'1','CARGO_BUILD_JOBS':'2','FE_REMOTE_CACHE_DIR':str(b/'ingot-cache')}
build=json.loads((b/'candidate-bootstrap/build.json').read_text());assert build['complete'];assert hashlib.sha256(Path(build['compiler']).read_bytes()).hexdigest()==build['compiler_sha256']
inputs=json.loads((b/'source-inputs.json').read_text())
def verify():
 changes=[name for name,sha in inputs.items() if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha]
 assert not changes,changes
verify()
subprocess.run(['python3',str(b/'workspace-report.py'),'suite-O1',build['compiler']],env=env,cwd='/dev/shm/fevm-mvs-runs',check=True)
verify()
print('Combined workspace measurement passed. Starting complete native acceptance.',flush=True)
with (b/'profile-monitor.log').open('wb') as log:
 profile=subprocess.Popen(['python3',str(b/'profile-candidate-o1.py')],env=env,cwd='/dev/shm/fevm-mvs-runs',stdout=log,stderr=subprocess.STDOUT)
 status=subprocess.run(['python3',str(b/'run-acceptance.py')],env=env,cwd='/dev/shm/fevm-mvs-runs').returncode
 profile_status=profile.wait(timeout=60)
verify()
print('Complete native acceptance status:',status,'profile:',profile_status,flush=True)
raise SystemExit(status)
