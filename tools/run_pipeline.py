import sys
import traceback

from tools.scrape_comments import run as scrape
from tools.classify_comments import run as classify
from tools.send_report import run as report


def run_pipeline():
    steps = [
        ("Scraping comments", scrape),
        ("Classifying comments", classify),
        ("Sending report", report),
    ]
    for name, step_fn in steps:
        print(f"\n{'='*50}")
        print(f"STEP: {name}")
        print(f"{'='*50}")
        try:
            step_fn()
        except Exception as e:
            print(f"\nERROR in '{name}': {e}")
            traceback.print_exc()
            sys.exit(1)
    print(f"\n{'='*50}")
    print("Pipeline complete!")
    print(f"{'='*50}")


if __name__ == "__main__":
    run_pipeline()
