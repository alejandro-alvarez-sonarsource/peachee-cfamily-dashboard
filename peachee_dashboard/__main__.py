import logging
import re
from argparse import ArgumentParser
from datetime import datetime
from typing import Dict, List, Tuple

import coloredlogs

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
    projects = None
    dates = []

    for build in builds:
        logger.info("Querying %s", build["id"])
        tasks = client.get_tasks(build["id"])

        if not projects:
            projects = {task["name"]: [] for task in tasks}

        dates.append(datetime.fromtimestamp(build["buildCreatedTimestamp"] / 1e3))

        missing = set(projects.keys())
        for task in tasks:
            projects[task["name"]].append(task)
            missing.remove(task["name"])

        for m in missing:
            projects[m] = {"status": "UNDEFINED"}

    return projects, dates


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
    parser.add_argument("--query-limit", type=int, default=5, help="GraphQL Query limit")
    parser.add_argument("--pattern", type=str, default="Cron", help="Job name pattern")
    opts = parser.parse_args(args=args)

    coloredlogs.install(
        level=opts.log_level.upper(),
        logger=logging.getLogger("peachee_dashboard"),
        fmt="%(asctime)s %(hostname)s %(name)s %(message)s",
    )

    client = CirrusCIClient(opts.cirrus_api)
    builds = get_filtered_builds(client, opts.repository, opts.branch, opts.query_limit, opts.pattern)
    projects, dates = get_task_matrix(client, builds)
