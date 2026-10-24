import collections,hashlib,json,re,sys,tarfile
from pathlib import Path
b=Path(__file__).resolve().parent
name=sys.argv[1]
rows=[];groups=collections.defaultdict(collections.Counter)
with tarfile.open(b/f'{name}-native-report.tar.gz','r|gz') as archive:
 for entry in archive:
  if entry.isfile() and entry.name.endswith('/tests.rmir'):
   text=archive.extractfile(entry).read().decode();headers=list(re.finditer(r'^    (\S+) \((?:private|internal|external), inline=.*$',text,re.M));keys=[]
   for i,h in enumerate(headers):
    end=headers[i+1].start() if i+1<len(headers) else text.rfind('}')
    fragment=text[h.start():end];fragment=fragment[fragment.index(' ('):].strip()
    keys.append(hashlib.sha256(fragment.encode()).hexdigest())
   suite=entry.name.split('/artifacts/native/')[0]
   groups[suite].update(keys)
   rows.append({'path':entry.name,'functions':len(headers),'rmir_sha256':hashlib.sha256(text.encode()).hexdigest()})
record={'modules':rows,'total_function_entries':sum(r['functions'] for r in rows),'groups':[{'suite':suite,'function_entries':sum(c.values()),'unique_owner_body_summaries':len(c),'duplicate_owner_body_entries':sum(c.values())-len(c)} for suite,c in groups.items()],'identity_scope':'Exact owner/inline metadata and full rendered runtime body within one suite/process; header display symbol excluded because package-specific conflicts change it. No cross-process Salsa identity comparison.'}
(b/f'{name}-inventory.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
