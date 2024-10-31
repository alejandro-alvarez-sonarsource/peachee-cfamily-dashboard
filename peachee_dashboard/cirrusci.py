import logging
import os
from typing import Dict, List

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

logger = logging.getLogger(__name__)


class CirrusCIClient:
    def __init__(self, endpoint: str):
        cookies = {}
        headers = {}
        if "CIRRUS_API_TOKEN" in os.environ:
            logger.info("Using Cirrus CI API with token")
            headers.update({"Authorization": f"Bearer {os.environ['CIRRUS_API_TOKEN']}"})
        elif "CIRRUS_COOKIE_HEADER" in os.environ:
            logger.info("Using Cirrus CI API with cookies")
            ch = os.environ["CIRRUS_COOKIE_HEADER"]
            cookies.update({x.split("=")[0].strip(): x.split("=")[1].strip() for x in ch.split(";")})
        else:
            raise ValueError("CIRRUS_API_TOKEN or CIRRUS_COOKIE_HEADER must be set on the environment")

        transport = AIOHTTPTransport(url=endpoint, cookies=cookies, headers=headers)
        self.client = Client(transport=transport, fetch_schema_from_transport=True)

        # Verify connectivity
        query = gql(
            """
            query {
                viewer {
                    id
                }
            }
            """
        )
        result = self.client.execute(query)
        if result["viewer"] is None:
            raise RuntimeError("Failed to connect to Cirrus CI API")

        logger.info("Connected to Cirrus CI API")

    def get_builds(self, repository: str, branch: str, limit: int) -> List[Dict]:
        query = gql(
            """
                query OwnerRepositoryQuery(
                $platform: String!
                $owner: String!
                $name: String!
                $branch: String
                $limit: Int!
                ) {
                ownerRepository(platform: $platform, owner: $owner, name: $name) {
                    ...RepositoryBuildList
                }
                }

                fragment RepositoryBuildList on Repository {
                builds(last: $limit, branch: $branch) {
                    edges {
                        node {
                            id
                            changeMessageTitle
                            status,
                            buildCreatedTimestamp
                        }
                    }
                }
                }
            """
        )
        result = self.client.execute(
            query,
            variable_values={
                "platform": "github",
                "owner": "SonarSource",
                "name": repository,
                "branch": branch,
                "limit": limit,
            },
        )
        return [e["node"] for e in result["ownerRepository"]["builds"]["edges"]]

    def get_tasks(self, build_id: str) -> List[Dict]:
        query = gql(
            """
                query BuildByIdQuery(
                $buildId: ID!
                ) {
                build(id: $buildId) {
                    ...BuildDetails
                }
                }

                fragment BuildDetails on Build {
                branch
                status
                buildCreatedTimestamp
                clockDurationInSeconds
                durationInSeconds
                latestGroupTasks {
                    ...TaskList
                }
                }

                fragment TaskList on Task {
                id
                name
                status
                executingTimestamp
                scheduledTimestamp
                finalStatusTimestamp
                durationInSeconds
                notifications {
                    message
                }
                firstFailedCommand {
                    name
                    status
                    durationInSeconds
                    logsTail
                }
                }
            """
        )
        result = self.client.execute(query, variable_values={"buildId": build_id})
        return result["build"]["latestGroupTasks"]

    def get_steps(self, task_id: str) -> List[Dict]:
        query = gql(
            """
                query TaskQuery(
                $taskId: ID!
                ) {
                task(id: $taskId) {
                    ...TaskDetails
                }
                }

                fragment TaskDetails on Task {
                commands {
                    name
                    durationInSeconds
                    status
                }
                }
            """
        )
        result = self.client.execute(query, variable_values={"taskId": task_id})
        return result["task"]["commands"]
