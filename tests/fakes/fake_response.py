"""Fake HTTP response for PreflightVerifier tests."""

from dataclasses import dataclass

import requests


@dataclass
class FakeResponse:
    status_code: int

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")