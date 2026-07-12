#!/usr/bin/env python3
"""Read-only drift audit for Git, MSU, GCP, and active containers."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
INVENTORY_PATH = Path(__file__).with_name("production_inventory.json")

TEXT_EXTENSIONS = {
    ".conf", ".css", ".html", ".js", ".jsx", ".json", ".md", ".py",
    ".r", ".svg", ".toml", ".ts", ".tsx", ".txt", ".yaml", ".yml",
}
DEPLOYMENT_PREFIXES = (
    ".claude/skills/",
    "backend/",
    "deploy/",
    "frontend/",
    "nginx/",
)
DEPLOYMENT_FILES = {"docker-compose.yml"}
RUNTIME_BACKEND_PREFIXES = (
    "backend/r_scripts/",
    "backend/renderers/",
    "backend/shared/",
    "backend/tools/",
    "backend/workers/",
    "backend/workflow/",
)
RUNTIME_BACKEND_FILES = {
    "backend/agent.py",
    "backend/config.py",
    "backend/main.py",
}

REMOTE_HASH_SCRIPT = r"""
import hashlib, json
from pathlib import Path

TEXT_EXTENSIONS = set(PAYLOAD_TEXT_EXTENSIONS)
payload = PAYLOAD
root = Path(payload["root"])
result = {}
for entry in payload["entries"]:
    path = root / entry["path"]
    if not path.is_file():
        result[entry["key"]] = None
        continue
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_EXTENSIONS or path.name == "Dockerfile":
        data = data.replace(b"\r\n", b"\n")
    result[entry["key"]] = hashlib.sha256(data).hexdigest()
print(json.dumps(result, sort_keys=True))
""".replace("PAYLOAD_TEXT_EXTENSIONS", repr(sorted(TEXT_EXTENSIONS)))

REMOTE_TREE_SCRIPT = r"""
import hashlib, json
from pathlib import Path

root = Path(PAYLOAD["root"])
result = {}
if root.is_dir():
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
print(json.dumps(result, sort_keys=True))
"""

REMOTE_FRONTEND_SCRIPT = r"""
root=/usr/share/nginx/html
index="$root/index.html"
[ -f "$index" ] || exit 0
printf 'index.html\t%s\n' "$(sha256sum "$index" | cut -d' ' -f1)"
grep -oE '(src|href)="/assets/[^"]+"' "$index" |
    cut -d'"' -f2 |
    sed 's#^/##' |
    sort -u |
    while IFS= read -r rel; do
        path="$root/$rel"
        if [ -f "$path" ]; then
            printf '%s\t%s\n' "$rel" "$(sha256sum "$path" | cut -d' ' -f1)"
        else
            printf '%s\t-\n' "$rel"
        fi
    done
"""


def run(command: list[str], *, input_text: str | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return completed.stdout


def normalized_hash(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_EXTENSIONS or path.name == "Dockerfile":
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def is_server_specific(path: str) -> bool:
    name = Path(path).name
    return (
        name.startswith(".env")
        or path.startswith("nginx/certs/") and name != ".gitkeep"
        or "/.pytest_cache/" in f"/{path}"
        or "__pycache__" in path
        or path.endswith((".pyc", ".pyo"))
    )


def tracked_deployment_paths() -> list[str]:
    output = run(["git", "ls-files", "--", "telecouplingAI-project"])
    paths = []
    prefix = "telecouplingAI-project/"
    for full_path in output.splitlines():
        if not full_path.startswith(prefix):
            continue
        path = full_path[len(prefix):]
        if is_server_specific(path):
            continue
        if path in DEPLOYMENT_FILES or path.startswith(DEPLOYMENT_PREFIXES):
            paths.append(path)
    return sorted(paths)


def local_manifest(paths: Iterable[str]) -> dict[str, str | None]:
    return {
        path: normalized_hash(PROJECT_ROOT / path)
        if (PROJECT_ROOT / path).is_file()
        else None
        for path in paths
    }


def ssh_python(
    host: str,
    script: str,
    payload: dict,
    *,
    container: str | None = None,
) -> dict[str, str | None]:
    program = f"PAYLOAD = {payload!r}\n{script}"
    encoded = base64.b64encode(program.encode("utf-8")).decode("ascii")
    if container:
        remote_command = (
            f"printf %s {encoded} | base64 -d | "
            f"docker exec -i {container} python3"
        )
    else:
        remote_command = f"printf %s {encoded} | base64 -d | python3"
    output = run(["ssh", "-o", "BatchMode=yes", host, remote_command])
    return json.loads(output)


def frontend_manifest(host: str, container: str) -> dict[str, str | None]:
    encoded = base64.b64encode(REMOTE_FRONTEND_SCRIPT.encode("utf-8")).decode("ascii")
    remote_command = (
        f"printf %s {encoded} | base64 -d | docker exec -i {container} sh"
    )
    output = run(["ssh", "-o", "BatchMode=yes", host, remote_command])
    result: dict[str, str | None] = {}
    for line in output.splitlines():
        path, digest = line.split("\t", maxsplit=1)
        result[path] = None if digest == "-" else digest
    return result


def compare(
    label: str,
    expected: dict[str, str | None],
    actual: dict[str, str | None],
) -> int:
    differences = []
    for path in sorted(set(expected) | set(actual)):
        if expected.get(path) != actual.get(path):
            differences.append(path)
    if not differences:
        print(f"PASS  {label}: {len(expected)} files")
        return 0
    print(f"FAIL  {label}: {len(differences)} differences")
    for path in differences[:50]:
        print(f"      {path}")
    if len(differences) > 50:
        print(f"      ... and {len(differences) - 50} more")
    return 1


def remote_source_manifest(host: str, root: str, paths: list[str]) -> dict[str, str | None]:
    entries = [{"key": path, "path": path} for path in paths]
    return ssh_python(host, REMOTE_HASH_SCRIPT, {"root": root, "entries": entries})


def container_manifest(
    host: str,
    container: str,
    mappings: dict[str, str],
) -> dict[str, str | None]:
    entries = [{"key": key, "path": path} for key, path in mappings.items()]
    return ssh_python(
        host,
        REMOTE_HASH_SCRIPT,
        {"root": "/", "entries": entries},
        container=container,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=INVENTORY_PATH,
        help="Production inventory JSON path",
    )
    parser.add_argument(
        "--skip-runtime",
        action="store_true",
        help="Compare host source only",
    )
    args = parser.parse_args()

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    paths = tracked_deployment_paths()
    local = local_manifest(paths)
    failures = 0

    runtime_paths = [
        path
        for path in paths
        if path in RUNTIME_BACKEND_FILES or path.startswith(RUNTIME_BACKEND_PREFIXES)
    ]
    runtime_expected = {path: local[path] for path in runtime_paths}
    runtime_mappings = {
        path: f"/app/{path.removeprefix('backend/')}" for path in runtime_paths
    }
    skill_paths = [path for path in paths if path.startswith(".claude/skills/")]
    skill_expected = {path: local[path] for path in skill_paths}
    skill_mappings = {
        path: f"/.claude/skills/{path.removeprefix('.claude/skills/')}"
        for path in skill_paths
    }

    frontend_manifests: dict[str, dict[str, str | None]] = {}
    guide_manifests: dict[str, dict[str, str | None]] = {}

    for name, server in inventory["servers"].items():
        host = server["ssh_host"]
        source = remote_source_manifest(host, server["project_root"], paths)
        failures += compare(f"{name} host source", local, source)

        if args.skip_runtime:
            continue

        for container in ("tele-backend", "tele-celery-render"):
            actual = container_manifest(host, container, runtime_mappings)
            failures += compare(
                f"{name} {container} backend runtime",
                runtime_expected,
                actual,
            )

        skills = container_manifest(host, "tele-backend", skill_mappings)
        failures += compare(f"{name} runtime skills", skill_expected, skills)

        frontend_manifests[name] = frontend_manifest(host, "tele-frontend")
        guide_manifests[name] = ssh_python(
            host,
            REMOTE_TREE_SCRIPT,
            {"root": server["user_guides_root"]},
        )

    if not args.skip_runtime and len(frontend_manifests) > 1:
        names = list(frontend_manifests)
        first = names[0]
        for name in names[1:]:
            failures += compare(
                f"{first}/{name} active frontend",
                frontend_manifests[first],
                frontend_manifests[name],
            )

    if not args.skip_runtime and len(guide_manifests) > 1:
        names = list(guide_manifests)
        first = names[0]
        for name in names[1:]:
            failures += compare(
                f"{first}/{name} user-guide assets",
                guide_manifests[first],
                guide_manifests[name],
            )

    if failures:
        print(f"\nProduction drift detected in {failures} scope(s).")
        return 1
    print("\nNo production drift detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
