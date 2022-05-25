set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/../test_functions.sh"

source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)" "talk.py"


function test_outputs(){
  additional_options="$1"
  output_file="${test_output_dir}/output_not_streaming.wav"
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

test_outputs --stream
test_outputs

function test_error_is_raised(){
  script_name="$1"
  exp_options="$2"
  expected_error="$3"
  test_name="$4"
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
  if [ -z "$(grep -F "${expected_error}" "${stderr_file}")" ]; then
    echo "A grpc error is expected if '${exp_options}'. "\
"An error '${expected_error}' is not found in file ${stderr_file}"
    exit 1
  fi
}

test_error_is_raised talk.py "--sample-rate-hz 2" "Invalid sample rate" "wrong_sample_rate"

test_error_is_raised talk.py "--language-code ru-RU" \
  "Model is not available on server: Voice English-US-Female-1 for language ru-RU not found." \
  "wrong_language"

test_error_is_raised talk.py "--output-device 0" "OSError:" "wrong_device"

test_error_is_raised talk.py "--voice foo" \
  "\"grpc_message\":\"Model is not available on server: Voice foo for language en-US not found. "\
"Please specify the voice name in your SynthesizeSpeechRequest.\"" \
  "wrong_voice"

test_list_devices tts/talk.py "Output"

set +e