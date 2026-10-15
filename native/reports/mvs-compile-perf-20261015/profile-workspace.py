import hashlib,json,os,subprocess,sys,time
from pathlib import Path
base=Path(__file__).resolve().parent
name,build_path=sys.argv[1:]
build=json.loads(Path(build_path).read_text())
compiler=build['compiler']
assert hashlib.sha256(Path(compiler).read_bytes()).hexdigest()==build['compiler_sha256']
command=[compiler,'test','--backend','native','--jobs','1','-O','1','/home/sean/code/fevm']
env={**os.environ,'TMPDIR':'/dev/shm/fevm-mvs-runs','RAYON_NUM_THREADS':'1','CARGO_BUILD_JOBS':'2','FE_REMOTE_CACHE_DIR':str(base/'ingot-cache'),'DEBUGINFOD_URLS':''}
profile=['perf','record','-e','task-clock:u','-F','49','--call-graph','dwarf,8192','--timestamp','-o',str(base/f'{name}.data'),'--','/usr/bin/time','-v',*command]
started=time.time()
with (base/f'{name}.log').open('wb') as log,(base/f'{name}-resources.jsonl').open('w',buffering=1) as samples:
 child=subprocess.Popen(profile,stdout=log,stderr=subprocess.STDOUT,env=env,cwd='/dev/shm/fevm-mvs-runs')
 while child.poll() is None:
  processes=[]
  for proc in Path('/proc').iterdir():
   if not proc.name.isdigit():continue
   try:
    argv=(proc/'cmdline').read_bytes().split(b'\0')
    if argv[0].decode()!=compiler:continue
    stat=(proc/'stat').read_text();fields=stat[stat.rfind(')')+2:].split()
    processes.append({'pid':int(proc.name),'cpu_seconds':(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK'),'rss_bytes':int(fields[21])*os.sysconf('SC_PAGE_SIZE')})
   except (OSError,ValueError,UnicodeError):pass
  samples.write(json.dumps({'time':time.time(),'compiler_processes':processes,'memory_pressure':Path('/proc/pressure/memory').read_text()})+'\n')
  time.sleep(5)
record={'complete':child.returncode==0,'status':child.returncode,'command':command,'profile_command':profile,'build':build,'started_unix':started,'finished_unix':time.time(),'wall_seconds':time.time()-started,'resource_log':f'{name}-resources.jsonl','log':f'{name}.log','scope':'One-thread O1 complete workspace test preparation and execution; user-CPU profile with 49Hz DWARF callgraphs, all subprocesses included.'}
(base/f'{name}.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='build'},indent=2))
sys.exit(child.returncode)
