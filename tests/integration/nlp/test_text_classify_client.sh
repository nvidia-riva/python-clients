# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/../helpers.sh"
source "$(dirname $0)/test_functions.sh"

source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)" "text_classify_client.py"

test_error_is_raised text_classify_client.py "--model foo" \
  "Error: Model foo is not a Riva API model, execution cannot be done" \
  "wrong_model"

test_for_specific_string text_classify_client.py "(['meteorology'], ["

set +e