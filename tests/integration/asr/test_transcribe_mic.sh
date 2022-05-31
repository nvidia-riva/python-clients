# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/../test_functions.sh"
source "$(dirname $0)/test_functions.sh"

source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)" "transcribe_mic.py"

test_string_presence transcribe_mic.py "--sample-rate-hz 2" "Invalid sample rate" "wrong_sample_rate" 1

test_list_devices asr/transcribe_mic.py Input
set +e