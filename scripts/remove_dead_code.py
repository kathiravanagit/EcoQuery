# scripts/remove_dead_code.py
"""Utility to detect and remove dead code from the EcoQuery project.

- Python dead code detection using `vulture`.
- TypeScript/React dead code detection using `ts-prune` (installed as a dev dependency).
- Unused files are moved to `dead_code_backup/` before deletion.
- A markdown report `dead_code_report.md` is generated summarizing actions.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = PROJECT_ROOT / "dead_code_backup"
REPORT_PATH = PROJECT_ROOT / "dead_code_report.md"

def ensure_backup_dir():
    BACKUP_DIR.mkdir(exist_ok=True)

def run_vulture() -> list[Path]:
    """Run vulture on the backend directory and return a list of dead file paths."""
    backend_path = PROJECT_ROOT / "backend"
    result = subprocess.run(["vulture", str(backend_path)], capture_output=True, text=True)
    dead_files: set[Path] = set()
    # Vulture output lines look like:
    #   path/to/file.py:123: 'some_func' is unused
    pattern = re.compile(r"^(.*?):\d+?:\s+'.*?' is unused")
    for line in result.stdout.splitlines():
        m = pattern.match(line.strip())
        if m:
            file_path = Path(m.group(1))
            dead_files.add(file_path)
    return list(dead_files)

def run_ts_prune() -> list[Path]:
    """Run ts-prune on the frontend src directory and return dead file paths.
    ts-prune prints lines like: `src/components/UnusedComponent.tsx` for each unused export.
    We treat each listed file as dead.
    """
    src_path = PROJECT_ROOT / "frontend" / "src"
    # Use npx to run ts-prune
    result = subprocess.run(["npx", "ts-prune", "--path", str(src_path)], capture_output=True, text=True, shell=True)
    dead_files: set[Path] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith("["):
            candidate = src_path / line
            if candidate.exists():
                dead_files.add(candidate)
    return list(dead_files)

def move_to_backup(paths: list[Path]):
    for p in paths:
        if not p.is_file():
            continue
        rel = p.relative_to(PROJECT_ROOT)
        dest = BACKUP_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(dest))

def generate_report(python_dead: list[Path], ts_dead: list[Path]):
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Dead Code Removal Report\n\n")
        f.write(f"Generated on: {"%Y-%m-%d %H:%M:%S" % __import__('datetime').datetime.now()}\n\n")
        f.write("## Python dead code files\n")
        for p in python_dead:
            f.write(f"- {p}\n")
        f.write("\n## TypeScript/React dead code files\n")
        for p in ts_dead:
            f.write(f"- {p}\n")
        f.write("\nAll listed files have been moved to `dead_code_backup/` for safe keeping.\n")

def main():
    ensure_backup_dir()
    python_dead = run_vulture()
    ts_dead = run_ts_prune()
    all_dead = python_dead + ts_dead
    if not all_dead:
        print("No dead code detected.")
        return
    move_to_backup(all_dead)
    generate_report(python_dead, ts_dead)
    print(f"Moved {len(all_dead)} dead files to backup and generated report at {REPORT_PATH}")

if __name__ == "__main__":
    main()
