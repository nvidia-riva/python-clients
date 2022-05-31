# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

from typing import Tuple
from unittest.mock import Mock


def set_auth_mock() -> Tuple[Mock, str]:
    auth = Mock()
    return_value_of_get_auth_metadata = 'return_value_of_get_auth_metadata'
    auth.get_auth_metadata = Mock(return_value=return_value_of_get_auth_metadata)
    return auth, return_value_of_get_auth_metadata
