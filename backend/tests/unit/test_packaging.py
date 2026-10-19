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


def test_ci_postgres_containers_create_the_database_the_init_script_grants_on():
    """The init script runs GRANT ... ON DATABASE mygovt, so a container started without POSTGRES_DB=mygovt
    aborts initialisation (first hosted CI run failed this way)."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    runs = [line for line in workflow.splitlines() if "docker run" in line and "mygovt-postgres" in workflow]
    starts = workflow.count("docker run -d --name pg")
    assert starts >= 1
    assert workflow.count("POSTGRES_DB=mygovt") == starts, runs


def _prod(name: str) -> str:
    return (ROOT / "docker" / name / "Dockerfile.prod").read_text(encoding="utf-8")


def test_production_images_are_not_dev_images():
    for name in ("backend", "frontend"):
        text = _prod(name)
        assert "--reload" not in text and "npm run dev" not in text
        assert "\nUSER " in text, f"{name}: production image must not run as root"
        assert "HEALTHCHECK" in text
    assert 'APP_ENV=production' in _prod("backend")
    assert "node:22" in _prod("frontend")                      # matches CI, not the dev image's node 20


def test_production_backend_installs_runtime_dependencies_only_and_ships_every_package():
    text = _prod("backend")
    assert "[all]" not in text and "[test" not in text         # no pytest/dev tools in the image
    assert "-e ." not in text
    cfg = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    assert "dependencies" in cfg["project"]                    # the Dockerfile reads this list
    assert "COPY --chown=mygovt:mygovt . ." in text            # `ai/` is not in setuptools packages, so source is copied


def test_production_frontend_only_copies_what_next_standalone_produces():
    text = _prod("frontend")
    assert ".next/standalone" in text and ".next/static" in text
    assert "output: 'standalone'" in (ROOT / "frontend" / "next.config.js").read_text(encoding="utf-8")
    assert "public" not in text or (ROOT / "frontend" / "public").exists()   # no COPY of a directory that does not exist
