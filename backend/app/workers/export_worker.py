import argparse
import os
import signal
import socket
import sys
import time
import uuid
from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.db.sqlite import init_db
from app.db.schema import init_schema
from app.services.exports.job_service import get_job_service
from app.services.exports.runner import JobRunner

logger = get_logger("export_worker")


class ExportWorker:
    """
    Independent background worker process that claims and executes pending export jobs.
    Runs separately from FastAPI without Celery/Redis dependencies.
    """

    def __init__(
        self,
        poll_interval: float = 2.0,
        stale_timeout_minutes: int = 15,
        run_once: bool = False,
    ):
        self.poll_interval = poll_interval
        self.stale_timeout_minutes = stale_timeout_minutes
        self.run_once = run_once
        self.running = True

        hostname = socket.gethostname()
        pid = os.getpid()
        self.worker_id = f"{hostname}:{pid}:{uuid.uuid4().hex[:6]}"

        self.job_service = get_job_service()
        self.runner = JobRunner()

        # Last maintenance sweep timestamp
        self._last_maintenance = 0.0

    def handle_signal(self, signum, frame):
        """Signal handler for graceful shutdown."""
        logger.info("Shutdown signal received (%s). Finishing active operations...", signum)
        self.running = False

    def perform_maintenance_if_needed(self):
        """Periodically recover stale jobs and clean up expired export files."""
        now = time.time()
        # Run every 60 seconds
        if now - self._last_maintenance > 60:
            try:
                self.job_service.recover_stale_jobs(self.stale_timeout_minutes)
                self.job_service.cleanup_expired_files()
            except Exception as exc:
                logger.warning("Error during worker maintenance sweep: %s", exc)
            self._last_maintenance = now

    def run(self):
        """Main worker polling loop."""
        logger.info("Export Worker [%s] started. Polling interval: %.1fs", self.worker_id, self.poll_interval)
        init_db()
        init_schema()

        while self.running:
            self.perform_maintenance_if_needed()

            try:
                # 1. Attempt to claim next pending job atomically
                job = self.job_service.claim_next_job(self.worker_id)

                if job:
                    logger.info("Processing job: %s ('%s')", job["id"], job["report_title"])
                    self.runner.process_job(job)

                    if self.run_once:
                        logger.info("Run-once flag active. Exiting after job completion.")
                        break
                    continue  # Immediately check for more jobs without sleeping

                if self.run_once:
                    logger.info("No pending jobs found and run-once flag is set. Exiting.")
                    break

                # No jobs claimed, sleep before next poll
                time.sleep(self.poll_interval)

            except Exception as exc:
                logger.error("Unexpected error in worker loop: %s", exc)
                time.sleep(self.poll_interval)

        logger.info("Export Worker [%s] stopped.", self.worker_id)


def main():
    setup_logging()

    parser = argparse.ArgumentParser(description="SSMS2XLS Independent Export Worker")
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Polling interval in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--stale-timeout",
        type=int,
        default=15,
        help="Minutes before considering an un-heartbeated job stale (default: 15)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one job (or exit if empty) without looping",
    )

    args = parser.parse_args()

    worker = ExportWorker(
        poll_interval=args.interval,
        stale_timeout_minutes=args.stale_timeout,
        run_once=args.once,
    )

    # Register OS signals
    signal.signal(signal.SIGINT, worker.handle_signal)
    signal.signal(signal.SIGTERM, worker.handle_signal)

    worker.run()


if __name__ == "__main__":
    main()

