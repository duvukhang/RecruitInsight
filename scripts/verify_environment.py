import importlib.metadata,json,platform,subprocess
from pathlib import Path
lock=Path('/app/backend/requirements.lock')
verified={}
for line in lock.read_text().splitlines():
    name,expected=line.split('==');actual=importlib.metadata.version(name)
    assert actual==expected,(name,expected,actual);verified[name]=actual
result={'result':'PASS','python':platform.python_version(),'dependencies':verified,
    'java':subprocess.run(['java','-version'],capture_output=True,text=True).stderr.splitlines()[0]}
print(json.dumps(result))
