import os
import subprocess
from pathlib import Path


def test_frontend_build_freshness_detects_missing_fresh_and_stale_output(tmp_path):
    frontend = tmp_path / "src" / "frontend"
    source = frontend / "src" / "App.jsx"
    output = frontend / "dist" / "index.html"
    source.parent.mkdir(parents=True)
    source.write_text("source")
    helper = Path(__file__).parents[1] / "scripts" / "frontend_needs_build.sh"

    def needs_build():
        return subprocess.run([str(helper)], cwd=tmp_path, check=False).returncode

    assert needs_build() == 0
    output.parent.mkdir()
    output.write_text("built")
    os.utime(source, (1, 1))
    os.utime(output, (2, 2))
    assert needs_build() == 1
    os.utime(source, (3, 3))
    assert needs_build() == 0
