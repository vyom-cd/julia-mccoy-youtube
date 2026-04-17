import logging
import sys
import traceback

from tools.scrape_comments import run as scrape
from tools.classify_comments import run as classify
from tools.send_report import run as report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pipeline")


def run_pipeline():
    steps = [
        ("Scraping comments", scrape),
        ("Classifying comments", classify),
        ("Sending report", report),
    ]
    for name, step_fn in steps:
        logger.info("=" * 50)
        logger.info("STEP: %s", name)
        logger.info("=" * 50)
        try:
            step_fn()
        except Exception as e:
            logger.error("ERROR in '%s': %s", name, e)
            traceback.print_exc()
            sys.exit(1)
    logger.info("=" * 50)
    logger.info("Pipeline complete!")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_pipeline()
