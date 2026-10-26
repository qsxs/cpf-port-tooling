"""受控单库 workflow 的固定引用、权限与制品范围静态检查。"""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
workflow = (ROOT / ".github/workflows/grid-producer.yml").read_text(encoding="utf-8")
expected = {"checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1", "setup-java": "b843ebf9b913146b38da2eaa7aeddf76074ae1ad",
            "setup-python": "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0", "upload-artifact": "cf430e030ddbb5b0abf93d22962f4752f3646cd9"}
refs = re.findall(r"uses: actions/([a-z-]+)@([0-9a-f]+)", workflow)
assert len(refs) == 6 and all(expected[name] == sha for name, sha in refs)
assert "workflow_dispatch:" in workflow and "contents: read" in workflow
assert "ubuntu-24.04" in workflow and "cancel-in-progress: false" in workflow
assert workflow.count("persist-credentials: false") == 2
assert "repository: qsxs/gridlayout-compose" in workflow and "java-version: '17'" in workflow and "python-version: '3.13'" in workflow
assert "actions/cache" not in workflow and "secrets." not in workflow
assert "if: success()" in workflow and "if: always()" in workflow
assert "/staging/" in workflow and "/evidence/" in workflow
assert "path: ${{ runner.temp }}/grid-producer-${{ github.run_id }}-${{ github.run_attempt }}/staging/" in workflow
assert "path: ${{ runner.temp }}/grid-producer-${{ github.run_id }}-${{ github.run_attempt }}/evidence/" in workflow
assert "run: python -B tooling/scripts/grid_producer.py" in workflow
script = (ROOT / "scripts/grid_producer.py").read_text(encoding="utf-8")
ast.parse(script)
assert '"Prepare", "Tasks", "Resolve", "Metadata", "NativeX64", "NativeArm64", "Publish", "Verify"' in script
assert 'GROUP = "com.github.qsxs.gridlayout-compose"' in script
assert "os.environ.copy" not in script and "GIT_COMMIT" not in script and "JITPACK" not in script
assert "grid / \"ohos/bootstrap-native.py\"" in script
assert 'output / "staging"' in script and 'output / "evidence"' in script
assert "deploy" not in workflow and "pages: write" not in workflow
print("CONTROLLED_PRODUCER_STATIC_CHECKS_PASSED_REAL_CI_NOT_RUN")
