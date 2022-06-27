# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e
source "$(dirname $0)/export_server_vars.sh"
source "$(dirname $0)/helpers.sh"

echo "Testing notebook tutorials/ASR.ipynb"
stdout_file="$(dirname $0)/asr/outputs/stdout_ASR_tutorial.txt"
stderr_file="$(dirname $0)/asr/outputs/stderr_ASR_tutorial.txt"
mkdir -p "$(dirname "${stdout_file}")"
set +e
jupyter nbconvert \
  --to notebook \
  --execute \
  --TagRemovePreprocessor.enabled=True \
  --TagRemovePreprocessor.remove_cell_tags do_not_test \
  --output-dir out \
  "$(dirname $0)/../../tutorials/ASR.ipynb" 1>"${stdout_file}" 2>"${stderr_file}"
retVal=$?
process_exit_status
rm -rf out

echo "Testing script transcribe_mic.py"
bash "$(dirname $0)/asr/test_transcribe_mic.sh"
echo "Testing script riva_streaming_asr_client.py ..."
bash "$(dirname $0)/asr/test_riva_streaming_asr_client.sh"
echo "Testing script transcribe_file_offline.py"
bash "$(dirname $0)/asr/test_transcribe_file_offline.sh"
echo "Testing script transcribe_file.py ..."
bash "$(dirname $0)/asr/test_transcribe_file.sh"

set +e