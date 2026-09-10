from __future__ import annotations

import argparse
import json

from app.config import Settings
from app.demo import run_all, write_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Legal RAG duplicate-data demo")
    parser.add_argument("command", choices=("run-all",))
    args = parser.parse_args()
    if args.command == "run-all":
        report = run_all(Settings.from_env())
        write_report(report)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

