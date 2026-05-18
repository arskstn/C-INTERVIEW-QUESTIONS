import re
from dataclasses import dataclass
from pathlib import Path

DIFFICULTY_RE = re.compile(r"^##\s+(.+)$")
QUESTION_RE = re.compile(r"^[ \t]{0,3}\d+\.\s+(.+)$")

REPO_ROOT = Path(__file__).parent.parent

DEFAULT_FILES = [
    "content/01_cpp/01_base.md",
    "content/01_cpp/02_types.md",
    "content/01_cpp/03_pointers.md",
    "content/01_cpp/04_memory.md",
]


@dataclass
class Question:
    text: str
    file_path: str
    section: str
    difficulty: str
    file_number: int


def parse_file(path: Path) -> list[Question]:
    rel = path.relative_to(REPO_ROOT)
    section = rel.parts[1]
    questions = []
    current_difficulty = "Unknown"
    file_number = 0

    for line in path.read_text(encoding="utf-8").splitlines():
        m = DIFFICULTY_RE.match(line)
        if m:
            current_difficulty = m.group(1).strip()
            continue
        m = QUESTION_RE.match(line)
        if m:
            file_number += 1
            questions.append(Question(
                text=m.group(1).strip(),
                file_path=str(rel),
                section=section,
                difficulty=current_difficulty,
                file_number=file_number,
            ))

    return questions


def parse_scope(file_paths: list[str] | None = None) -> list[Question]:
    paths = file_paths or DEFAULT_FILES
    content_root = REPO_ROOT / "content"
    result = []
    for p in paths:
        full = (REPO_ROOT / p).resolve()
        # Reject paths that escape the content/ directory
        try:
            full.relative_to(content_root.resolve())
        except ValueError:
            continue
        if full.exists():
            result.extend(parse_file(full))
    return result
