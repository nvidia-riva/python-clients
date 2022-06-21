# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/../helpers.sh"
source "$(dirname $0)/test_functions.sh"

source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)" "eval_intent_slot.py"

test_error_is_raised intentslot_client.py "--model foo" \
  "Error: Model foo is not a Riva API model, execution cannot be done" \
  "wrong_model"

function test_on_small_file(){
  additional_options="$1"
  input_file="$(dirname $0)/../../../data/nlp_test_metrics/weather.fixed.eval.small.tsv"
  reference_file="$(dirname $0)/reference_outputs/eval_intent_slot_small_metrics.txt"
  exp_options="--input-file ${input_file}"
  if [ ! -z "${additional_options}" ]; then
    exp_options="${exp_options} ${additional_options}"
  fi
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout.txt"
  stderr_file="${test_output_dir}/stderr.txt"
  set +e
  python "scripts/nlp/eval_intent_slot.py" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  num_lines_in_reference="$(cat "${reference_file}" | wc -l)"
  line_i=1
  while read hyp_line <&3 && read ref_line <&4; do
    ref_line="$(echo "${ref_line}" | tr -d '\n\r')"
    if [[ "${hyp_line}" != "${ref_line}" ]]; then
      echo "${line_i}th line in outputs does not match reference."
      echo "hypothesis: '${hyp_line}'"
      echo "reference:  '${ref_line}'"
      exit 1
    fi
    ((++line_i))
  done 3< <(sed -n "1,${num_lines_in_reference}p" "${stdout_file}") 4<"${reference_file}"
}

test_on_small_file "--max-async-requests-to-queue 0"

test_on_small_file

set +e