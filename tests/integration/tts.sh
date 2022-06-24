# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e
source "$(dirname $0)/export_server_vars.sh"
source "$(dirname $0)/helpers.sh"

echo "Testing notebook tutorials/TTS.ipynb"
stdout_file="$(dirname $0)/tts/outputs/stdout_TTS_tutorial.txt"
stderr_file="$(dirname $0)/tts/outputs/stderr_TTS_tutorial.txt"
mkdir -p "$(dirname "${stdout_file}")"
set +e
jupyter nbconvert \
  --to notebook \
  --execute \
  --TagRemovePreprocessor.enabled=True \
  --TagRemovePreprocessor.remove_cell_tags do_not_test \
  --output-dir out \
  "$(dirname $0)/../../tutorials/TTS.ipynb" 1>"${stdout_file}" 2>"${stderr_file}"
retVal=$?
process_exit_status
rm -rf out
rm tutorials/my_{offline,streaming}_synthesized_speech.wav

echo "Testing script talk.py"
bash "$(dirname $0)/tts/test_talk.sh"

set +e