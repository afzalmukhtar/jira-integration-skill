"""Async Jira REST API client with connection pooling, rate limiting, and retry logic.

Reads auth from environment variables:
    JIRA_BASE_URL  - e.g. https://your-instance.atlassian.net
    JIRA_USER      - email address
    JIRA_API_TOKEN - API token from id.atlassian.com
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

import aiohttp

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_CONCURRENT = 10  # semaphore limit for parallel requests
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # seconds – exponential backoff base
TIMEOUT_SECONDS = 30


@dataclass
class JiraConfig:
    """Resolved configuration from environment variables."""

    base_url: str
    user: str
    api_token: str
    project_key: str
    account_id: str = ""
    story_type_id: str = "10001"
    subtask_type_id: str = "10003"
    task_type_id: str = "10002"
    bug_type_id: str = "10004"
    component_id: str = ""
    sprint_id: str = ""
    sprint_field: str = "customfield_10020"

    @classmethod
    def from_env(cls) -> "JiraConfig":
        base_url = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
        user = os.environ.get("JIRA_USER", "")
        token = os.environ.get("JIRA_API_TOKEN", "")
        if not all([base_url, user, token]):
            print(
                "ERROR: JIRA_BASE_URL, JIRA_USER, and JIRA_API_TOKEN must be set.",
                file=sys.stderr,
            )
            sys.exit(1)
        return cls(
            base_url=base_url,
            user=user,
            api_token=token,
            project_key=os.environ.get("JIRA_PROJECT_KEY", ""),
            account_id=os.environ.get("JIRA_ACCOUNT_ID", ""),
            story_type_id=os.environ.get("JIRA_STORY_TYPE_ID", "10001"),
            subtask_type_id=os.environ.get("JIRA_SUBTASK_TYPE_ID", "10003"),
            task_type_id=os.environ.get("JIRA_TASK_TYPE_ID", "10002"),
            bug_type_id=os.environ.get("JIRA_BUG_TYPE_ID", "10004"),
            component_id=os.environ.get("JIRA_COMPONENT_ID", ""),
            sprint_id=os.environ.get("JIRA_SPRINT_ID", ""),
            sprint_field=os.environ.get("JIRA_SPRINT_FIELD", "customfield_10020"),
        )


# ---------------------------------------------------------------------------
# Async client
# ---------------------------------------------------------------------------


@dataclass
class JiraClient:
    """Async Jira REST API v3 client with concurrency control and retry."""

    config: JiraConfig
    _session: aiohttp.ClientSession | None = field(default=None, repr=False)
    _semaphore: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(MAX_CONCURRENT))

    # -- lifecycle -----------------------------------------------------------

    async def __aenter__(self) -> "JiraClient":
        self._session = self._build_session()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    def _build_session(self) -> aiohttp.ClientSession:
        creds = f"{self.config.user}:{self.config.api_token}"
        b64 = base64.b64encode(creds.encode()).decode()
        headers = {
            "Authorization": f"Basic {b64}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        connector = aiohttp.TCPConnector(ssl=False, limit=MAX_CONCURRENT)
        return aiohttp.ClientSession(
            base_url=self.config.base_url,
            headers=headers,
            timeout=timeout,
            connector=connector,
        )

    # -- low-level request with retry ---------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> dict | list | None:
        """Execute an HTTP request with semaphore, retry, and backoff."""
        assert self._session is not None, "Client not initialised – use `async with`"
        async with self._semaphore:
            last_exc: Exception | None = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    async with self._session.request(
                        method, path, json=json_body, params=params
                    ) as resp:
                        if resp.status == 429:
                            retry_after = int(resp.headers.get("Retry-After", attempt * 2))
                            await asyncio.sleep(retry_after)
                            continue
                        body_text = await resp.text()
                        if resp.status >= 400:
                            raise JiraAPIError(resp.status, body_text, path)
                        if not body_text:
                            return None
                        return json.loads(body_text)
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    last_exc = exc
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
            raise JiraAPIError(0, str(last_exc), path)

    # -- high-level helpers --------------------------------------------------

    async def get_myself(self) -> dict:
        return await self._request("GET", "/rest/api/3/myself")

    async def search(
        self,
        jql: str,
        fields: str = "key,summary,status,issuetype,parent,assignee,priority",
        max_results: int = 100,
        start_at: int = 0,
    ) -> dict:
        params = {
            "jql": jql,
            "fields": fields,
            "maxResults": str(max_results),
            "startAt": str(start_at),
        }
        return await self._request("GET", "/rest/api/3/search", params=params)

    async def get_issue(self, key: str) -> dict:
        return await self._request("GET", f"/rest/api/3/issue/{key}")

    async def create_issue(self, payload: dict) -> dict:
        return await self._request("POST", "/rest/api/3/issue", json_body=payload)

    async def get_transitions(self, key: str) -> list[dict]:
        data = await self._request("GET", f"/rest/api/3/issue/{key}/transitions")
        return data.get("transitions", [])

    async def transition_issue(self, key: str, transition_id: str) -> None:
        await self._request(
            "POST",
            f"/rest/api/3/issue/{key}/transitions",
            json_body={"transition": {"id": transition_id}},
        )

    async def add_comment(self, key: str, body_text: str) -> dict:
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": body_text}],
                    }
                ],
            }
        }
        return await self._request(
            "POST", f"/rest/api/3/issue/{key}/comment", json_body=payload
        )

    async def update_issue(self, key: str, fields: dict) -> None:
        await self._request(
            "PUT", f"/rest/api/3/issue/{key}", json_body={"fields": fields}
        )

    async def get_project(self, key: str) -> dict:
        return await self._request("GET", f"/rest/api/3/project/{key}")

    async def get_board_sprints(self, board_id: str, state: str = "active") -> list[dict]:
        data = await self._request(
            "GET",
            f"/rest/agile/1.0/board/{board_id}/sprint",
            params={"state": state},
        )
        return data.get("values", [])

    async def get_boards(self, project_key: str) -> list[dict]:
        data = await self._request(
            "GET",
            "/rest/agile/1.0/board",
            params={"projectKeyOrId": project_key},
        )
        return data.get("values", [])

    # -- helpers for common patterns ----------------------------------------

    def build_issue_payload(
        self,
        summary: str,
        *,
        issue_type_id: str | None = None,
        description: str = "",
        parent_key: str = "",
        project_key: str = "",
    ) -> dict:
        """Build a Jira issue creation payload."""
        pkey = project_key or self.config.project_key
        type_id = issue_type_id or self.config.task_type_id

        fields: dict[str, Any] = {
            "project": {"key": pkey},
            "summary": summary,
            "issuetype": {"id": type_id},
        }
        if description:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            }
        if parent_key:
            fields["parent"] = {"key": parent_key}
        if self.config.account_id:
            fields["assignee"] = {"accountId": self.config.account_id}
            fields["reporter"] = {"accountId": self.config.account_id}
        if self.config.component_id:
            fields["components"] = [{"id": self.config.component_id}]
        if self.config.sprint_id and self.config.sprint_field:
            fields[self.config.sprint_field] = int(self.config.sprint_id)
        return {"fields": fields}

    async def find_transition_id(self, key: str, target_name: str) -> str | None:
        """Find a transition ID by matching status name (case-insensitive)."""
        transitions = await self.get_transitions(key)
        target_lower = target_name.lower()
        for t in transitions:
            if target_lower in t["name"].lower() or target_lower in t.get("to", {}).get("name", "").lower():
                return t["id"]
        return None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class JiraAPIError(Exception):
    def __init__(self, status: int, body: str, path: str) -> None:
        self.status = status
        self.body = body
        self.path = path
        super().__init__(f"Jira API {status} on {path}: {body[:500]}")


# ---------------------------------------------------------------------------
# Convenience: run async main from sync context
# ---------------------------------------------------------------------------


def run_async(coro):
    """Utility to run an async coroutine from a sync script entry point."""
    return asyncio.run(coro)
