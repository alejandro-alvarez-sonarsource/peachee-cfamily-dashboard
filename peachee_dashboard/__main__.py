import logging
import re
import shutil
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import coloredlogs
from jinja2 import Environment, PackageLoader

from peachee_dashboard.cirrusci import CirrusCIClient
from peachee_dashboard.dashboard import Dashboard

logger = logging.getLogger(__name__)


def get_filtered_builds(client: CirrusCIClient, repository: str, branch: str, query_limit: int, pattern: str):
    pattern = re.compile(pattern)
    builds = client.get_builds(repository, branch, query_limit)
    builds = [build for build in builds if pattern.match(build["changeMessageTitle"])]
    for b in builds:
        logger.debug("Found build %s", b["changeMessageTitle"])
    return builds


def get_task_matrix(client: CirrusCIClient, builds: List[Dict]) -> Dashboard:
    projects = set()
    dates = []
    table = []

    for build in builds:
        logger.info("Querying build %s", build["id"])
        tasks = client.get_tasks(build["id"])

        dates.append(datetime.fromtimestamp(build["buildCreatedTimestamp"] / 1e3))

        row = {}
        for task in tasks:
            projects.add(task["name"])
            row[task["name"]] = task
            if task["status"] in ("FAILED", "ABORTED"):
                logger.info("Querying failure reasons for task %s", task["id"])
                task.update(client.get_failure_reason(task["id"]))

        table.append(row)

    projects = list(projects)
    projects.sort(key=lambda p: p.lower())
    return Dashboard(projects, dates, table)


def asset_symlink(src: Path, dst: Path):
    if dst.exists():
        dst.unlink()
    logger.info("Symlink %s => %s", src, dst)
    dst.symlink_to(src)


def asset_copy(src: Path, dst: Path):
    if dst.exists():
        dst.unlink()
    logger.info("Copy %s => %s", src, dst)
    shutil.copy(src, dst)


def copy_assets(output_dir: Path, symlink: bool):
    asset_action = asset_symlink if symlink else asset_copy

    p = Path(__file__).parent / "templates"
    for source in (t for t in p.iterdir() if t.is_file() and t.suffix != ".jinja"):
        target = output_dir / source.name
        asset_action(source, target)


def main(args: List[str] = None):
    parser = ArgumentParser()
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument(
        "--cirrus-api",
        type=str,
        default="https://api.cirrus-ci.com/graphql",
        help="Cirrus CI API URL",
    )
    parser.add_argument("--repository", type=str, default="peachee-cfamily", help="Repository name")
    parser.add_argument("--branch", type=str, default="cirrusci", help="Branch name")
    parser.add_argument("--query-limit", type=int, default=30, help="GraphQL Query limit")
    parser.add_argument("--limit", type=int, default=14, help="Number of builds to list")
    parser.add_argument("--pattern", type=str, default="Cron", help="Job name pattern")
    parser.add_argument("--output-dir", type=Path, default="/tmp/peachee_dashboard")
    parser.add_argument(
        "--symlink-assets",
        default=False,
        action="store_true",
        help="Symlink instead of copying assets to the output directory",
    )
    opts = parser.parse_args(args=args)

    coloredlogs.install(
        level=opts.log_level.upper(),
        logger=logging.getLogger("peachee_dashboard"),
        fmt="%(asctime)s %(hostname)s %(name)s %(message)s",
    )

    client = CirrusCIClient(opts.cirrus_api)
    builds = get_filtered_builds(client, opts.repository, opts.branch, opts.query_limit, opts.pattern)[: opts.limit]
    dashboard = get_task_matrix(client, builds)

    logger.info("Got %d entries", len(dashboard))

    loader = PackageLoader("peachee_dashboard")
    env = Environment(loader=loader, autoescape=True)
    env.globals["zip"] = zip
    env.globals["status_icon"] = status_icon
    env.globals["status_title"] = status_title

    logger.info("Generating index.html")
    index_template = env.get_template("index.jinja")
    opts.output_dir.mkdir(exist_ok=True)
    with open(opts.output_dir / "index.html", "w") as fd:
        fd.write(index_template.render(dashboard=dashboard))

    copy_assets(opts.output_dir, opts.symlink_assets)


TASK_ICON_MAP = {
    "checkout": "bi-git",
    "build": "bi-gear-wide-connected",
    "build2": "bi-gear-wide-connected",
    "bwrapper_analyze": "bi-patch-check",
    "external_compdb_analyze": "bi-patch-check",
    "analyze2": "bi-patch-check",
    "analyze_autoscan": "bi-robot",
    "autoscan_result_test": "bi-robot",
}


def status_icon(task: Dict) -> str:
    if ffc := task.get("firstFailedCommand", None):
        return TASK_ICON_MAP.get(ffc["name"], "bi-list-task")
    elif notifications := task.get("notifications", None):
        if notifications and notifications[-1]["message"] == "CI agent stopped responding!":
            return "bi-lightbulb-off"
    return "bi-search"


def status_title(task: Dict) -> str:
    extra = ""
    if task.get("notifications", None):
        extra = task["notifications"][-1]["message"]

    if ffc := task.get("firstFailedCommand", None):
        log_tail = ffc["logsTail"][-1] if ffc["logsTail"] else ""
        if log_tail in ("Context canceled!", "Timed out!"):
            extra = log_tail
        return f"{ffc['name']} {ffc['status']} {extra}"
    return f"{task["status"]} {extra}"
