"""Pytest configuration and fixtures for peermodel tests."""

import pytest
from peermodel.sync import set_test_db_connection


@pytest.fixture(autouse=True)
def auto_setup_test_db(request):
    """Automatically set up test database connection for tests that need it.

    This fixture is autouse=True, so it runs for every test. It checks if the
    test has a test_db_connection fixture and registers it with SyncManager
    for incremental_sync tests that need it.
    """
    # Only set it if the test actually uses test_db_connection
    if 'test_db_connection' in request.fixturenames:
        # Get the fixture value dynamically
        test_db_connection = request.getfixturevalue('test_db_connection')
        set_test_db_connection(test_db_connection)
        yield
        # Clean up after the test
        set_test_db_connection(None)
    else:
        yield
