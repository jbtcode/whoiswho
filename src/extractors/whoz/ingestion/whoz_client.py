"""
whoz_client.py — Reusable WHOZ API client with authentication, pagination, and helpers.
"""

import os
import time
import requests
from typing import Optional, Dict, Any, Generator, List

class WhozAuth:
    """Handles OAuth2 client credentials authentication for the WHOZ API."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        token_path: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        grant_type: Optional[str] = None,
    ):
        self.api_url = (api_url or os.environ["WHOZ_API_URL"]).rstrip("/")
        self.token_path = token_path or os.environ["WHOZ_TOKEN_PATH"]
        self.client_id = client_id or os.environ["WHOZ_CLIENT_ID"]
        self.client_secret = client_secret or os.environ["WHOZ_CLIENT_SECRET"]
        self.grant_type = grant_type or os.environ.get("WHOZ_GRANT_TYPE", "client_credentials")

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    @property
    def token_url(self) -> str:
        return f"{self.api_url}/{self.token_path}"

    def _fetch_token(self) -> Dict[str, Any]:
        response = requests.post(
            self.token_url,
            data={
                "grant_type": self.grant_type,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()

    def get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        token_data = self._fetch_token()
        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 300)
        self._token_expires_at = time.time() + expires_in - 60
        return self._access_token


class WhozClient:
    """Reusable HTTP client for the WHOZ API with auth, headers, and pagination."""

    DEFAULT_API_VERSION = "V19"

    def __init__(self, auth: Optional[WhozAuth] = None, api_version: Optional[str] = None):
        self.auth = auth or WhozAuth()
        self.api_version = api_version or self.DEFAULT_API_VERSION
        self.base_url = self.auth.api_url
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.auth.get_access_token()}",
            "Content-Type": "application/json",
            "Accept-Version": self.api_version,
        }

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint: str, json_body: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.post(url, headers=self._get_headers(), json=json_body)
        response.raise_for_status()
        return response.json()

    def paginate_list(
        self,
        endpoint: str,
        body: Dict[str, Any],
        max_pages: Optional[int] = None,
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Iterate through paginated list responses.
        Yields chunks (lists) of entities. Follows the `next` continuation
        token until exhausted or max_pages is reached.
        """
        current_body = body.copy()
        page_count = 0

        while True:
            response = self.post(endpoint, json_body=current_body)
            data = response.get("data", [])
            metadata = response.get("metadata", {})

            if data:
                yield data

            page_count += 1
            next_token = metadata.get("next")

            if not next_token:
                break
            if max_pages and page_count >= max_pages:
                break

            current_body["next"] = next_token

    def fetch_by_entity_ids(
        self,
        endpoint: str,
        entity_ids: List[str],
        batch_size: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Fetch full entity details in batches of ≤50 (WHOZ limit for full data).
        """
        results = []
        for i in range(0, len(entity_ids), batch_size):
            batch = entity_ids[i : i + batch_size]
            response = self.post(endpoint, json_body={"entityIds": batch})
            results.extend(response.get("data", []))
        return results


def get_env_config() -> Dict[str, str]:
    """Load common WHOZ configuration from environment variables."""
    return {
        "workspace_id": os.environ["WHOZ_WORKSPACE_ID"],
        "federation_id": os.environ["WHOZ_FEDERATION_ID"],
    }
