"""
Export all questions from content/ to a numbered txt file.
Usage: python scripts/export_questions.py [output.txt]
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

import re
DIFFICULTY_RE = re.compile(r"^##\s+(.+)$")
QUESTION_RE = re.compile(r"^[ \t]{0,3}(\d+)\.\s+(.+)$")


def export(out_path: Path) -> None:
    files = sorted((REPO_ROOT / "content").rglob("*.md"))
    global_n = 0

    with out_path.open("w", encoding="utf-8") as f:
        for md in files:
            rel = md.relative_to(REPO_ROOT)
            section = rel.parts[1]
            current_difficulty = "Unknown"
            file_questions = []

            for line in md.read_text(encoding="utf-8").splitlines():
                m = DIFFICULTY_RE.match(line)
                if m:
                    current_difficulty = m.group(1).strip()
                    continue
                m = QUESTION_RE.match(line)
                if m:
                    file_questions.append((current_difficulty, m.group(2).strip()))

            if not file_questions:
                continue

            f.write(f"\n{'=' * 72}\n")
            f.write(f"# {rel}\n")
            f.write(f"{'=' * 72}\n\n")

            for difficulty, text in file_questions:
                global_n += 1
                f.write(f"[{global_n}] [{section} | {difficulty}]\n")
                f.write(f"{text}\n\n")

    print(f"Экспортировано {global_n} вопросов → {out_path}")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "questions_export.txt"
    export(out)
