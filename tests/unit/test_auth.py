# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

from unittest.mock import Mock, patch

import grpc

from riva.client.auth import create_channel, Auth


@patch("grpc.insecure_channel", Mock(return_value="insecure_channel"))
def test_create_channel() -> None:
    channel = create_channel()
    assert channel == "insecure_channel"


class TestAuth:
    @patch("grpc.insecure_channel", Mock(return_value="insecure_channel"))
    def test_channel_is_set(self) -> None:
        auth = Auth()
        assert auth.channel == "insecure_channel"

    def test_get_auth_metadata(self) -> None:
        auth = Auth()
        metadata = auth.get_auth_metadata()
        assert metadata == []
