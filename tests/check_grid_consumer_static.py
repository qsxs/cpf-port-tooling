"""consumer 工作流、工具白名单与编译验收边界的静态检查。"""
import ast
import hashlib
import json
from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parents[1]
project = ROOT / "consumers/grid"
manifest = json.loads((project / "toolchain-inputs.json").read_text(encoding="utf-8"))
assert manifest["sourceCommit"] == "ed3472803fdb637d601391f62f43aba1bfea551f"
assert len(manifest["files"]) == 13
assert all(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) and item["size"] > 0 for item in manifest["files"])
assert all('/src/' not in item['path'] and 'sources.jar' not in item['path'] for item in manifest['files'])
assert all(item['url'] == 'https://raw.githubusercontent.com/qsxs/gridlayout-compose/' + manifest['sourceCommit'] + '/ohos/' + item['path'] for item in manifest['files'])
workflow = yaml.load((ROOT / ".github/workflows/grid-consumer.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
assert set(workflow['on']) == {'workflow_dispatch'}
assert set(workflow['on']['workflow_dispatch']['inputs']) == {'version','source_sha'}
assert workflow['permissions'] == {'contents':'read'}
assert workflow['jobs']['consumer']['runs-on'] == 'ubuntu-24.04'
steps = workflow['jobs']['consumer']['steps']
assert len([step for step in steps if step.get('uses','').startswith('actions/checkout@')]) == 1
assert steps[0]['with']['persist-credentials'] == 'false' and 'repository' not in steps[0]['with']
expected = {'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1','actions/setup-java@b843ebf9b913146b38da2eaa7aeddf76074ae1ad','actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0','actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9'}
assert {step['uses'] for step in steps if 'uses' in step} == expected
assert steps[-1]['if'] == 'always()' and '/evidence/' in steps[-1]['with']['path']
settings = (project/'settings.gradle.kts').read_text(encoding='utf-8')
build = (project/'build.gradle.kts').read_text(encoding='utf-8')
script = (ROOT/'scripts/grid_remote_consumer.py').read_text(encoding='utf-8')
for forbidden in ['mavenLocal(', 'includeBuild(', 'frozen-maven', 'repositories/cpf-maven', 'GRID_CHECKOUT']:
    assert forbidden not in settings + build + script
assert 'exclusiveContent' in settings and 'https://qsxs.github.io/cpf-maven/' in settings
assert 'implementation("$gridGroup:grid:$gridVersion")' in build
assert 'implementation("$gridGroup:grid-ohos' not in build
assert 'compiler.compilerPluginClasspath?.files' in build and 'compiler.libraries.files' in build
assert 'metadataTrace(compiler)' in build and 'sha(probe) == probeSha' in build
assert 'Grid artifact differs from anonymous HTTP' in build and 'targets == setOf(target)' in build
assert 'response.read()' in script and 'TRANSPORT_INCOMPLETE_READ' in script
assert 'ProxyHandler({})' in script and 'LD_LIBRARY_PATH' in script and 'os.environ.copy()' not in script
assert '"Tasks", "Resolve", "Metadata", "NativeX64", "NativeArm64"' in script
assert 'REQUIRED.issubset(names)' in script and 'verify_records(output)' in script
assert (project/'src/commonMain/kotlin/GridConsumer.kt').read_text(encoding='utf-8').count('VerticalGrid(columns = SimpleGridCells.Fixed(2))') == 1
for path in [ROOT/'scripts/grid_remote_consumer.py',ROOT/'tests/test_grid_remote_consumer.py']:
    ast.parse(path.read_text(encoding='utf-8'))
print('GRID_CONSUMER_STATIC_CHECKS_PASSED_REAL_CONSUMER_NOT_RUN')
