# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/../helpers.sh"
source "$(dirname $0)/test_functions.sh"

source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)" "ner_client.py"


test_error_is_raised intentslot_client.py "--model foo" \
  "Error: Model foo is not a Riva API model, execution cannot be done" \
  "wrong_model"


function test(){
  test_mode="$1"
  expected_output="$2"
  exp_options="--test ${test_mode}"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_${test_mode}.txt"
  stderr_file="${test_output_dir}/stderr_${test_mode}.txt"
  set +e
  python "scripts/nlp/ner_client.py" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  found_required_output="$(grep -F "${expected_output}" "${stdout_file}" | wc -l)"
  if ((found_required_output < 1)); then
    echo "FAILED. Expected output \"${expected_output}\" is not found. See full output in file ${stdout_file}."
    exit 1
  fi
}

test_modes=(
  label
  span_start
  span_end
)

expected_outputs=(
  "[['LOC'], ['PER', 'ORG']]"
  "[[9], [0, 27]]"
  "[[21], [11, 44]]"
)

test "${test_modes[0]}" "${expected_outputs[0]}"
test "${test_modes[1]}" "${expected_outputs[1]}"
test "${test_modes[2]}" "${expected_outputs[2]}"

set +e