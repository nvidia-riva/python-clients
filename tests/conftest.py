# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

"""Pytest configuration and shared fixtures."""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: tests requiring a running Riva server (deselect with '-m \"not integration\"')"
    )
    config.addinivalue_line(
        "markers", "benchmark: performance benchmark tests (select with '-m benchmark')"
    )
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (auto-handled by pytest-asyncio)"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests when RIVA_URI is not set."""
    import os

    if os.getenv("RIVA_URI"):
        # RIVA_URI is set, don't skip integration tests
        return

    skip_integration = pytest.mark.skip(reason="RIVA_URI not set")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
