import logging
import re
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import coloredlogs
from jinja2 import Environment, PackageLoader

from peachee_dashboard.cirrusci import CirrusCIClient

logger = logging.getLogger(__name__)


def get_filtered_builds(client: CirrusCIClient, repository: str, branch: str, query_limit: int, pattern: str):
    pattern = re.compile(pattern)
    builds = client.get_builds(repository, branch, query_limit)
    builds = [build for build in builds if pattern.match(build["changeMessageTitle"])]
    for b in builds:
        logger.debug("Found build %s", b["changeMessageTitle"])
    return builds


def get_task_matrix(client: CirrusCIClient, builds: List[Dict]) -> Tuple[Dict, List[datetime]]:
    projects = set()
    dates = []
    table = []

    for build in builds:
        logger.info("Querying %s", build["id"])
        tasks = client.get_tasks(build["id"])

        dates.append(datetime.fromtimestamp(build["buildCreatedTimestamp"] / 1e3))

        row = {}
        for task in tasks:
            projects.add(task["name"])
            row[task["name"]] = task

        table.append(row)

    projects = list(projects)
    projects.sort(key=lambda p: p.lower())
    return projects, list(zip(dates, table))


def main(args: List[str] = None):
    parser = ArgumentParser()
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument(
        "--cirrus-api",
        type=str,
        default="https://api.cirrus-ci.com/graphql",
        help="Cirrus CI API URL",
    )
    parser.add_argument("--repository", type=str, default="peachee-cfamily", help="Repository name")
    parser.add_argument("--branch", type=str, default="cirrusci", help="Branch name")
    parser.add_argument("--query-limit", type=int, default=30, help="GraphQL Query limit")
    parser.add_argument("--limit", type=int, default=20, help="Number of builds to list")
    parser.add_argument("--pattern", type=str, default="Cron", help="Job name pattern")
    parser.add_argument("--output-dir", type=Path, default="/tmp/peachee_dashboard")
    opts = parser.parse_args(args=args)

    coloredlogs.install(
        level=opts.log_level.upper(),
        logger=logging.getLogger("peachee_dashboard"),
        fmt="%(asctime)s %(hostname)s %(name)s %(message)s",
    )

    client = CirrusCIClient(opts.cirrus_api)
    builds = get_filtered_builds(client, opts.repository, opts.branch, opts.query_limit, opts.pattern)[: opts.limit]
    projects, matrix = get_task_matrix(client, builds)

    logger.info("Got %d entries", len(matrix))

    loader = PackageLoader("peachee_dashboard")
    env = Environment(loader=loader, autoescape=True)

    logger.info("Generating index.html")
    index_template = env.get_template("index.jinja")
    opts.output_dir.mkdir(exist_ok=True)
    with open(opts.output_dir / "index.html", "w") as fd:
        fd.write(index_template.render(projects=projects, matrix=matrix))

    p = Path(__file__).parent / "templates"
    for t in (t for t in p.iterdir() if t.is_file() and t.suffix != ".jinja"):
        target = opts.output_dir / t.name
        if not target.exists():
            logger.info("Symlink %s", t)
            target.symlink_to(t)
