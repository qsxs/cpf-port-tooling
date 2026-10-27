"""检查声明验证器能区分类自有方法和 Any 的继承方法；夹具保留。"""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import poko_remote_consumer as consumer

HEADER = "public final class acceptance/PokoConsumerProbe : kotlin/Any {\n"
METHODS = "    public open operator fun equals(other: kotlin/Any?): kotlin/Boolean\n    public open fun hashCode(): kotlin/Int\n    public open fun toString(): kotlin/String\n"
SIGNATURES = "\n".join("acceptance/PokoConsumerProbe." + name + "|" + name + "(){}[0]" for name in ("equals", "hashCode", "toString"))


class OwnDeclarationsTest(unittest.TestCase):
    def setUp(self):
        local = ROOT / ".local"
        local.mkdir(exist_ok=True)
        self.fixture = Path(tempfile.mkdtemp(prefix="poko-declarations-", dir=local))
        (self.fixture / "evidence").mkdir()
        self.klib = self.fixture / "probe.klib"
        self.klib.write_bytes(b"fixture")
        self.compilation = {"outputs": [{"path": str(self.klib)}], "irPayload": True}

    def inspect(self, metadata, signatures):
        def run(argv, **kwargs):
            return SimpleNamespace(returncode=0, stderr="", stdout=metadata if argv[1] == "dump-metadata" else signatures)
        with patch.object(consumer.subprocess, "run", side_effect=run):
            return consumer.own_declarations(self.fixture, self.compilation, "fixture", self.fixture, {})

    def test_all_three_methods_are_declared_by_probe_class(self):
        result = self.inspect(HEADER + METHODS + "}\n", SIGNATURES)
        self.assertEqual(set(result["methods"]), {"equals", "hashCode", "toString"})

    def test_methods_outside_probe_class_do_not_count_as_own(self):
        with self.assertRaisesRegex(RuntimeError, "does not declare generated equals"):
            self.inspect(HEADER + "}\n" + METHODS, SIGNATURES)

    def test_missing_class_signature_fails(self):
        with self.assertRaisesRegex(RuntimeError, "does not declare generated toString"):
            self.inspect(HEADER + METHODS + "}\n", "\n".join(SIGNATURES.splitlines()[:2]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
