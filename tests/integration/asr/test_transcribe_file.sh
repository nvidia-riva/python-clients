# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/../test_functions.sh"
source "$(dirname $0)/test_functions.sh"

source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)" "transcribe_file.py"


function test_verbose_format(){
  input_file="en-US_sample.wav"
  exp_options="--input-file data/examples/${input_file} --print-confidence"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_verbose_format.txt"
  stderr_file="${test_output_dir}/stderr_verbose_format.txt"
  set +e
  python "scripts/asr/transcribe_file.py" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  number_of_stability_messages="$(grep -F "Stability:" "${stdout_file}" | wc -l)"
  number_of_confidence_messages="$(grep -F "Confidence:" "${stdout_file}" | wc -l)"
  if ((number_of_stability_messages < 1 || number_of_confidence_messages < 1)); then
    echo "FAILED. Verbose format is wrong. Expected at least 1 stability message and at least 1 confidence message, "\
"whereas ${number_of_stability_messages} stability messages found and ${number_of_confidence_messages} confidence "\
"messages found. See ${stdout_file}."
    exit 1
  fi
}


test_verbose_format


test_list_devices asr/transcribe_file.py Output


function test_show_intermediate(){
  input_file="en-US_sample.wav"
  exp_options="--input-file data/examples/${input_file} --show-intermediate"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_show_intermediate.txt"
  stderr_file="${test_output_dir}/stderr_show_intermediate.txt"
  set +e
  python "scripts/asr/transcribe_file.py" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  number_of_intermediate_prints="$(grep -F ">>" "${stdout_file}" | wc -l)"
  if ((number_of_intermediate_prints < 1)); then
    echo "FAILED. When option --show-intermediate is provided, there has to be at least 1 intermediate print "\
"whereas no intermediate prints were found. Intermediate prints start with '>>'. See ${stdout_file}."
    exit 1
  fi
}


test_show_intermediate
test_simulate_realtime transcribe_file.py
test_string_presence \
  transcribe_file.py \
  "--input-file data/examples/en-US_sample.wav --language-code ru-RU" \
  "details = \"Error: Unavailable model requested. Lang: ru-RU, Type: online\"" \
  language_code_ru_RU \
  1
test_transcript_affecting_params transcribe_file.py

set +e