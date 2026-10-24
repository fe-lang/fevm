import hashlib,json,shutil,sys
from pathlib import Path
base=Path(__file__).resolve().parent
name=sys.argv[1]
artifacts=[x for line in (base/f'{name}-build.jsonl').read_text().splitlines() if (x:=json.loads(line)).get('reason')=='compiler-artifact' and x.get('executable') and x['target']['name']=='sonatina_codegen']
assert len(artifacts)==1
binary=base/f'{name}-tests'
assert not binary.exists()
shutil.copy2(artifacts[0]['executable'],binary)
record={'binary':str(binary),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'source_base':'1544e570257cbb1e453283b8a81b25b828ec3ca0','production_source_sha256':hashlib.sha256((base/('object_initialization.baseline.rs' if name.startswith('join-baseline') else 'object_initialization.candidate.rs')).read_bytes()).hexdigest(),'probe_source_sha256':hashlib.sha256((base/'join-benchmark.rs').read_bytes()).hexdigest(),'probe_temporary_and_excluded_from_production_commit':True}
(base/f'{name}-binary.json').write_text(json.dumps(record,indent=2)+'\n')
print(binary)
