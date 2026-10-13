"""Inspect publishable files and existing Git history without printing secret values."""

import json
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{30,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    config = dotenv_values(ROOT / ".env")
    secrets = [
        config[key]
        for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "API_TOKEN")
        if config.get(key)
    ]
    candidates = sorted(
        set(
            git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
            .decode("utf-8")
            .strip("\0")
            .split("\0")
        )
    )
    findings = []

    def inspect(content, location):
        text = content.decode("utf-8", errors="ignore")
        if any(secret in text for secret in secrets) or any(
            pattern.search(text) for pattern in PATTERNS
        ):
            findings.append(
                {"location": location, "issue": "possible credential/private key"}
            )

    for name in candidates:
        path = ROOT / name
        if not path.is_file():
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            findings.append(
                {"location": name, "issue": "environment file is publishable"}
            )
        if path.suffix.lower() in {".pdf", ".faiss", ".db", ".sqlite", ".sqlite3"}:
            findings.append(
                {"location": name, "issue": "private/generated data is publishable"}
            )
        if any(
            part in {".logs", "node_modules", ".next", ".venv", "__pycache__"}
            for part in path.parts
        ):
            findings.append(
                {"location": name, "issue": "runtime/build artifact is publishable"}
            )
        inspect(path.read_bytes(), name)

    history_blobs = 0
    for line in git("rev-list", "--objects", "--all").decode("utf-8").splitlines():
        object_id = line.split(" ", 1)[0]
        if git("cat-file", "-t", object_id).strip() == b"blob":
            history_blobs += 1
            inspect(
                git("cat-file", "blob", object_id), f"history blob {object_id[:12]}"
            )
    inspect(git("log", "--all", "--format=%B"), "commit messages")
    images = re.findall(
        r"!\[[^\]]*\]\(([^)]+)\)", (ROOT / "README.md").read_text(encoding="utf-8")
    )
    for image in images:
        if not image.startswith("https://") and not (ROOT / image).is_file():
            findings.append({"location": image, "issue": "README image is missing"})
    report = {
        "status": "pass" if not findings else "fail",
        "source_files": len(candidates),
        "history_blobs": history_blobs,
        "readme_images": len(images),
        "findings": findings,
    }
    output = ROOT / ".logs/publication-audit.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__":
    main()
