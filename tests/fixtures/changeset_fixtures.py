"""Fixtures for changeset fetcher integration tests."""

import pytest

@pytest.fixture
def pr_fixture(request):
    """Parametrized fixture resolving to private_pr_fixtures or public_pr_fixtures.

    Used with @pytest.mark.parametrize(indirect=True) to run a single test
    method against multiple PR scenarios.
    """
    return request.getfixturevalue(request.param)
