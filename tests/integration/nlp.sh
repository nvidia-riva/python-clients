# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e
source "$(dirname $0)/export_server_vars.sh"
source "$(dirname $0)/helpers.sh"

echo "Testing notebook tutorials/NLP.ipynb"
stdout_file="$(dirname $0)/nlp/outputs/stdout_NLP_tutorial.txt"
stderr_file="$(dirname $0)/nlp/outputs/stderr_NLP_tutorial.txt"
mkdir -p "$(dirname "${stdout_file}")"
set +e
jupyter nbconvert \
  --to notebook \
  --execute \
  --TagRemovePreprocessor.enabled=True \
  --TagRemovePreprocessor.remove_cell_tags do_not_test \
  --output-dir out \
  "$(dirname $0)/../../tutorials/NLP.ipynb" 1>"${stdout_file}" 2>"${stderr_file}"
retVal=$?
process_exit_status
rm -rf out

echo "Testing script eval_intent_slot.py"
bash "$(dirname $0)/nlp/test_eval_intent_slot.sh"

echo "Testing script classify_client.py"
bash "$(dirname $0)/nlp/test_text_classify_client.sh"

echo "Testing script qa_client.py"
bash "$(dirname $0)/nlp/test_qa_client.sh"

echo "Testing script punctuation_client.py"
bash "$(dirname $0)/nlp/test_punctuation_client.sh"

echo "Testing script ner_client.py"
bash "$(dirname $0)/nlp/test_ner_client.sh"

echo "Testing script intentslot_client.py"
bash "$(dirname $0)/nlp/test_intentslot_client.sh"

set +e