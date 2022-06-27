# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/../test_functions.sh"

source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)" "talk.py"


function test_string_presence(){
  exp_options="$1"
  expected_string="$2"
  test_name="$3"
  stderr="$4"
  inputs=(
    "Please, tell me the weather tomorrow."
    "What is weather tomorrow?"
  )
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_${test_name}.txt"
  stderr_file="${test_output_dir}/stderr_${test_name}.txt"
  set +e
  for query in "${inputs[@]}"; do
    echo "${query}"
  done | python "scripts/tts/talk.py" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  set -e
  if [[ "${stderr}" == 1 ]]; then
    check_file="${stderr_file}"
  else
    check_file="${stdout_file}"
  fi
  if [ -z "$(grep -F "${expected_string}" "${check_file}")" ]; then
    echo "FAILED: a string '${expected_string}' is expected in ${check_file} if options are '${exp_options}'."
    exit 1
  fi
}

test_string_presence "--play-audio" "Time spent:" "not_streaming" 0

test_string_presence "--play-audio --stream" "Time to first audio:" "streaming" 0

test_string_presence "--sample-rate-hz 2 --play-audio" "Invalid sample rate" "wrong_sample_rate" 1

test_string_presence "--play-audio --language-code ru-RU" \
  "Model is not available on server: Voice  for language ru-RU not found." \
  "wrong_language" \
  1

test_string_presence "--play-audio --voice foo" \
  "\"grpc_message\":\"Model is not available on server: Voice foo for language en-US not found. "\
"Please specify the voice name in your SynthesizeSpeechRequest.\"" \
  "wrong_voice" \
  1

test_list_devices tts/talk.py "Output"

function test_outputs(){
  additional_options="$1"
  output_file="${test_output_dir}/$2"
  reference_file="$(dirname $0)/reference_outputs/2_phrases.wav"
  exp_options="--output ${output_file} ${additional_options}"
  inputs=(
    "Please, tell me the weather tomorrow."
    "What is weather tomorrow?"
  )
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_not_streaming.txt"
  stderr_file="${test_output_dir}/stderr_not_streaming.txt"
  set +e
  for query in "${inputs[@]}"; do
    echo "${query}"
  done | python "scripts/tts/talk.py" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  set -e
  is_equal="$(python -c "hf=open('${output_file}', 'rb');rf=open('${reference_file}', 'rb');print(int(hf.read()==rf.read()))")"
  if ((is_equal<1)); then
    echo "FAILED: output file ${output_file} and reference file ${reference_file} are not equal."
    exit 1
  fi
}

test_outputs --stream output_streaming.wav
test_outputs "" output_not_streaming.wav

set +e