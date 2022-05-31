# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

function test_for_specific_string(){
  script_name="$1"
  expected_string="$2"
  exp_options=""
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout.txt"
  stderr_file="${test_output_dir}/stderr.txt"
  set +e
  python "scripts/nlp/${script_name}" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  found_result="$(grep -F "${expected_string}" "${stdout_file}" | wc -l)"
  if ((found_result < 1)); then
    echo "FAILED: no results were found in standard output. "\
"Results were searched by string '${expected_string}'. Standard output in file ${stdout_file}"
    exit 1
  fi
}


function test_error_is_raised(){
  script_name="$1"
  exp_options="$2"
  expected_error="$3"
  test_name="$4"
  input_file="en-US_sample.wav"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_${test_name}.txt"
  stderr_file="${test_output_dir}/stderr_${test_name}.txt"
  set +e
  python "scripts/nlp/${script_name}" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  set -e
  if [ -z "$(grep -F "${expected_error}" "${stderr_file}")" ]; then
    echo "A grpc error is expected if '${exp_options}'. "\
"An error '${expected_error}' is not found in file ${stderr_file}"
    exit 1
  fi
}