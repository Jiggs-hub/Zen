import argparse
import json
from pathlib import Path

from pipeline import run_batch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Clara assignment automation pipeline.")
    parser.add_argument("--demo-dir", default="inputs/demo", help="Directory containing demo transcripts/forms.")
    parser.add_argument("--onboarding-dir", default="inputs/onboarding", help="Directory containing onboarding transcripts/forms.")
    parser.add_argument("--output-dir", default="outputs/accounts", help="Directory to store per-account outputs.")
    parser.add_argument("--tracker-file", default="tracker/tasks.json", help="Task tracker JSON path.")
    parser.add_argument("--run-log", default="changelog/pipeline_runs.jsonl", help="Pipeline run log file path.")
    parser.add_argument(
        "--mode",
        choices=["all", "demo", "onboarding"],
        default="all",
        help="Run only demo stage, only onboarding stage, or both.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_batch(
        demo_dir=Path(args.demo_dir),
        onboarding_dir=Path(args.onboarding_dir),
        output_root=Path(args.output_dir),
        tracker_file=Path(args.tracker_file),
        mode=args.mode,
        run_log_path=Path(args.run_log),
    )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
