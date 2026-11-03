"""Analyze a recording from the command line (development aid):

    uv run python -m app.cli recording.mp3 --out report.md
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from app.pipeline import analyze
from app.report import render_markdown
from app.settings import Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Voices analysis pipeline on one audio file.")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--out", type=Path, help="write the Markdown report here (default: stdout)")
    parser.add_argument("--json", type=Path, help="also write the raw analysis as JSON")
    args = parser.parse_args(argv)
    settings = Settings.from_env()

    started = time.monotonic()
    last_stage = ""

    def progress(fraction: float, stage: str) -> None:
        nonlocal last_stage
        if stage != last_stage:
            last_stage = stage
            print(f"[{time.monotonic() - started:6.1f}s] {fraction * 100:5.1f}%  {stage}", file=sys.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"input{args.audio.suffix.lower()}"
        shutil.copy(args.audio, src)
        analysis = analyze(src, args.audio.name, progress, settings)

    markdown = render_markdown(analysis)
    if args.out:
        args.out.write_text(markdown)
    else:
        print(markdown)
    if args.json:
        args.json.write_text(json.dumps(analysis.to_dict(), indent=2, ensure_ascii=False))
    print(f"done in {time.monotonic() - started:.1f}s (audio {analysis.duration:.0f}s, threads {settings.threads})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
