import ast
import os
from pathlib import Path

def test_no_async_def_in_services_and_api():
    """
    Step 6 verification test:
    Scans all python files in src/app/services/ and src/app/api/
    and asserts that 0 async def function/method definitions exist.
    """
    root_dir = Path(__file__).parent.parent / "src" / "app"
    target_dirs = [root_dir / "services", root_dir / "api"]

    async_defs = []

    for target_dir in target_dirs:
        for py_file in target_dir.glob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.AsyncFunctionDef):
                    async_defs.append(f"{py_file.name}:{node.lineno} -> async def {node.name}")

    assert len(async_defs) == 0, f"Found unexpected async def statements: {async_defs}"
