"""Packaging / container-build prerequisites that previously failed only inside `docker build`."""
import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_build_backend_is_importable():
    """Regression: `setuptools.backends.legacy:build` does not exist, so `pip install -e .` (the backend
    Dockerfile) failed with BackendUnavailable before any application code ran."""
    cfg = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    module, _, attr = cfg["build-system"]["build-backend"].partition(":")
    mod = importlib.import_module(module)
    assert hasattr(mod, attr) if attr else hasattr(mod, "build_wheel")


def test_dockerignore_keeps_host_artifacts_out_of_images():
    front = (ROOT / "frontend" / ".dockerignore").read_text(encoding="utf-8").split()
    back = (ROOT / "backend" / ".dockerignore").read_text(encoding="utf-8").split()
    assert {"node_modules", ".next", ".env"} <= set(front)          # host node_modules must not overwrite the image's
    assert {"__pycache__", ".coverage", ".env"} <= set(back)
    assert "!.env.example" in front and "!.env.example" in back


def test_every_dockerfile_copy_source_exists():
    import re

    for df in (ROOT / "docker").glob("*/Dockerfile"):
        ctx = {"backend": ROOT / "backend", "frontend": ROOT / "frontend", "postgres": ROOT / "docker" / "postgres"}[df.parent.name]
        for line in df.read_text(encoding="utf-8").splitlines():
            m = re.match(r"COPY\s+(?!--from)(.+?)\s+\S+$", line.strip())
            if not m:
                continue
            for src in m.group(1).split():
                if src in (".", "./"):
                    continue
                pattern = src.rstrip("*") if src.endswith("*") else src
                assert list(ctx.glob(src)) or (ctx / pattern).exists(), f"{df}: COPY source '{src}' not found in build context {ctx}"
