import json,os,subprocess,sys,time
from pathlib import Path
base=Path('/tmp/fevm-mvs-compile-perf-20261015-r1')
compiler=str(base/'candidate-bootstrap/bin/fe')
command=['/usr/bin/time','-v',sys.executable,'/home/sean/code/fevm/native/accept.py','--build',str(base/'candidate-bootstrap/build.json'),'--out',str(base/'acceptance'),'--check-only','--stage-timeout','7200','--build-timeout','1800']
with (base/'acceptance.log').open('wb') as log, (base/'resources.jsonl').open('w',buffering=1) as samples:
    child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
    while child.poll() is None:
        measurements=[]
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():continue
            try:
                argv=(proc/'cmdline').read_bytes().split(b'\0')
                if argv[0].decode()!=compiler:continue
                stat=(proc/'stat').read_text();fields=stat[stat.rfind(')')+2:].split()
                measurements.append({'pid':int(proc.name),'cpu_seconds':(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK'),'rss_bytes':int(fields[21])*os.sysconf('SC_PAGE_SIZE'),'arguments':[a.decode() for a in argv if a]})
            except (OSError,ValueError,UnicodeError):pass
        samples.write(json.dumps({'time':time.time(),'compiler_processes':measurements,'memory_pressure':Path('/proc/pressure/memory').read_text(),'meminfo':Path('/proc/meminfo').read_text()})+'\n')
        time.sleep(10)
    sys.exit(child.returncode)
