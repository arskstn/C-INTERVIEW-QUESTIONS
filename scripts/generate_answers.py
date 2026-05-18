#!/usr/bin/env python3
"""
Generate quiz answer options for all questions using OpenAI API.

Usage:
    python scripts/generate_answers.py --key sk-...
    python scripts/generate_answers.py --key sk-... --batch 25 --model gpt-4o-mini
    python scripts/generate_answers.py --key sk-... --start 1000 --end 2000
    python scripts/generate_answers.py --key sk-... --dry-run

Resumes automatically: already-answered qids in output file are skipped.

Cost estimate (gpt-4o-mini):
    ~18 000 questions, batch 30 → ~600 API calls
    ~2 500 input tokens/call + ~1 500 output tokens/call
    Input:  600 × 2500 × $0.15/1M ≈ $0.23
    Output: 600 × 1500 × $0.60/1M ≈ $0.54
    Total:  ~$0.77 for all 18 000 questions
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Generate quiz answers via OpenAI")
    p.add_argument(
        "--key",
        default=None,
        help="OpenAI API key. Falls back to OPENAI_API_KEY env var if omitted.",
    )
    p.add_argument("--output", default="answers.jsonl", help="Output JSONL file (default: answers.jsonl)")
    p.add_argument("--questions", default="questions_export.txt", help="Questions file")
    p.add_argument("--batch", type=int, default=30, help="Questions per API call (default: 30)")
    p.add_argument("--model", default="gpt-4o-mini", help="OpenAI model (default: gpt-4o-mini)")
    p.add_argument("--start", type=int, default=1, help="Start from qid (inclusive)")
    p.add_argument("--end", type=int, default=None, help="Stop at qid (inclusive)")
    p.add_argument("--dry-run", action="store_true", help="Parse questions and show stats, no API calls")
    p.add_argument("--delay", type=float, default=0.5, help="Delay between API calls in seconds (default: 0.5)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Parse questions_export.txt
# ---------------------------------------------------------------------------

QID_RE = re.compile(r"^\[(\d+)\]\s+\[.*?\]\s*$")


def load_questions(path: str) -> dict[int, str]:
    """Returns {qid: question_text}."""
    questions = {}
    current_qid = None
    current_text_lines = []

    def flush():
        if current_qid is not None:
            text = " ".join(current_text_lines).strip()
            if text:
                questions[current_qid] = text

    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        m = QID_RE.match(line)
        if m:
            flush()
            current_qid = int(m.group(1))
            current_text_lines = []
        elif current_qid is not None and line and not line.startswith("===") and not line.startswith("#"):
            current_text_lines.append(line)

    flush()
    return questions


def load_done_qids(output_path: str) -> set[int]:
    done = set()
    p = Path(output_path)
    if not p.exists():
        return done
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            done.add(int(obj["qid"]))
        except (json.JSONDecodeError, KeyError):
            pass
    return done


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are generating quiz answer options for C++ and systems-programming interview questions.
The quiz is displayed in a GUI with 4 buttons, so answers must be SHORT: 4–12 words each.

Rules:
- correct: the actual right answer, concise and unambiguous
- wrong: three plausible distractors — similar length and style to the correct answer, but factually wrong
- Do NOT include the question text in the answer
- Do NOT start answers with "A:", "Answer:", numbers, or dashes
- Keep all answers in the SAME LANGUAGE as the question (Russian questions → Russian answers)

Respond ONLY with a valid JSON object:
{"results": [{"qid": <number>, "correct": "<answer>", "wrong": ["<w1>", "<w2>", "<w3>"]}, ...]}"""


def build_user_message(batch: list[tuple[int, str]]) -> str:
    lines = ["Generate answers for these questions:"]
    for qid, text in batch:
        lines.append(f"[{qid}] {text}")
    return "\n".join(lines)


def call_api(client, model: str, batch: list[tuple[int, str]], retries: int = 5) -> list[dict]:
    delay = 2.0
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_message(batch)},
                ],
                temperature=0.7,
            )
            raw = response.choices[0].message.content
            data = json.loads(raw)
            results = data.get("results", [])
            return results
        except Exception as e:
            err = str(e)
            if "rate_limit" in err.lower() or "429" in err:
                print(f"  Rate limit, waiting {delay:.0f}s...", flush=True)
                time.sleep(delay)
                delay = min(delay * 2, 60)
            elif attempt < retries - 1:
                print(f"  Error: {e}. Retrying in {delay:.0f}s...", flush=True)
                time.sleep(delay)
                delay *= 2
            else:
                print(f"  Failed after {retries} attempts: {e}", flush=True)
                return []
    return []


def validate_result(obj: dict) -> bool:
    if not isinstance(obj, dict):
        return False
    if not isinstance(obj.get("qid"), int):
        return False
    if not isinstance(obj.get("correct"), str) or not obj["correct"].strip():
        return False
    wrong = obj.get("wrong", [])
    if not isinstance(wrong, list) or len(wrong) != 3:
        return False
    if not all(isinstance(w, str) and w.strip() for w in wrong):
        return False
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    print(f"Loading questions from {args.questions}...")
    all_questions = load_questions(args.questions)
    print(f"  Loaded {len(all_questions)} questions")

    done_qids = load_done_qids(args.output)
    if done_qids:
        print(f"  Resuming: {len(done_qids)} already answered, skipping")

    end_qid = args.end or max(all_questions.keys())
    pending = [
        (qid, text)
        for qid, text in sorted(all_questions.items())
        if args.start <= qid <= end_qid and qid not in done_qids
    ]

    if not pending:
        print("Nothing to do — all questions already answered.")
        return

    total = len(pending)
    batches = [pending[i:i + args.batch] for i in range(0, total, args.batch)]
    print(f"  {total} questions to process in {len(batches)} batches of {args.batch}")

    if args.dry_run:
        print("\nDry run — no API calls made.")
        print(f"Example first batch qids: {[q[0] for q in batches[0][:5]]}")
        return

    import os
    api_key = args.key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OpenAI API key required: pass --key or set OPENAI_API_KEY env var")
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        print("openai package not found. Run: pip install openai")
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    out_file = Path(args.output)
    answered = 0
    skipped = 0
    start_time = time.time()

    with out_file.open("a", encoding="utf-8") as f:
        for batch_idx, batch in enumerate(batches):
            qids_in_batch = [q[0] for q in batch]
            elapsed = time.time() - start_time
            rate = answered / elapsed if elapsed > 0 else 0
            remaining = total - answered - skipped
            eta = f"{remaining / rate / 60:.0f}min" if rate > 0 else "?"
            print(
                f"Batch {batch_idx + 1}/{len(batches)} | "
                f"qids {qids_in_batch[0]}-{qids_in_batch[-1]} | "
                f"done {answered + len(done_qids)}/{len(all_questions)} | "
                f"ETA {eta}",
                flush=True,
            )

            results = call_api(client, args.model, batch)

            result_map = {}
            for obj in results:
                if validate_result(obj):
                    result_map[int(obj["qid"])] = obj

            for qid, _ in batch:
                if qid in result_map:
                    line = json.dumps(result_map[qid], ensure_ascii=False)
                    f.write(line + "\n")
                    answered += 1
                else:
                    print(f"  WARNING: no valid result for qid {qid}", flush=True)
                    skipped += 1

            f.flush()

            if batch_idx < len(batches) - 1:
                time.sleep(args.delay)

    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.0f}s")
    print(f"  Answered: {answered}")
    print(f"  Skipped/failed: {skipped}")
    print(f"  Output: {out_file.resolve()}")
    if skipped:
        print(f"  Re-run the script to retry failed questions (they were not written to output)")


if __name__ == "__main__":
    main()
