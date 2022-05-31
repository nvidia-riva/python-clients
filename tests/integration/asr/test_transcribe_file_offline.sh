# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/test_functions.sh"

source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)" "transcribe_file_offline.py"

test_string_presence \
  transcribe_file_offline.py \
  "--input-file examples/en-US_sample.wav --language-code ru-RU" \
  "Error: Model is not available on server" \
  language_code_ru_RU \
  0
test_transcript_affecting_params transcribe_file_offline.py
set +e