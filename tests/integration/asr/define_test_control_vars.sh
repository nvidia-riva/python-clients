# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

if [[ "${script_name}" == "riva_streaming_asr_client.py" ]]; then
  use_stdout_for_testing=0
  time_info_before_final_transcript=1
  test_max_alternatives=1
else
  use_stdout_for_testing=1
  time_info_before_final_transcript=0
  test_max_alternatives=0
fi

if [[ "${script_name}" == "transcribe_file_offline.py" ]]; then
  offline=1
else
  offline=0
fi