"""
generate_build_info.py — Roda no build da imagem Docker (backend).

Lê o HEAD do repositório git (copiado para o contexto de build) e grava
/app/build_info.json com o commit rodando na imagem. Usado pelo endpoint
GET /api/status/deploy para permitir verificação remota, sem SSH, de que
o código na VM está sincronizado com o GitHub.
"""
import json
import subprocess
from datetime import datetime, timezone


def _git(fmt: str) -> str:
    return subprocess.check_output(
        ["git", "log", "-1", f"--format={fmt}"], cwd="/app"
    ).decode().strip()


def main() -> None:
    info = {
        "git_commit_hash": _git("%H"),
        "git_commit_date": _git("%cI"),
        "git_commit_message": _git("%s"),
        "build_time": datetime.now(timezone.utc).isoformat(),
    }
    with open("/app/build_info.json", "w") as f:
        json.dump(info, f)


if __name__ == "__main__":
    main()
