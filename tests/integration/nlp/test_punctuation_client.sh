set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/../helpers.sh"

test_output_dir="$(dirname $0)/outputs/test_punctuation_client"
mkdir -p "${test_output_dir}"
rm -rf "${test_output_dir}"/*


function test_not_interactive(){
  exp_options=""
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_not_interactive.txt"
  stderr_file="${test_output_dir}/stderr_not_interactive.txt"
  expected_output="Can you prove that you are self aware?"
  set +e
  python "scripts/nlp/punctuation_client.py" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  found_expected="$(grep -F "${expected_output}" "${stdout_file}" | wc -l)"
  if ((found_expected < 1)); then
    echo "FAILED. Expected output '${expected_output}' is not found in stdout file ${stdout_file}"
    exit 1
  fi
}

test_not_interactive


function test_interactive(){
  inputs=(
    "can you prove that you are self aware"
    "edmund i was king of the english from 939 until his death he was a son of king edward the elder "\
"and his third wife eadgifu and a grandson of alfred the great"
  )
  expected_outputs=(
    "Can you prove that you are self aware?"
    "Edmund I was king of the English from 939 until his death. He was a son of King Edward the Elder "\
"and his third wife Eadgifu, and a grandson of Alfred the Great."
  )
  exp_options="--interactive"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_interactive.txt"
  stderr_file="${test_output_dir}/stderr_interactive.txt"
  set +e
  for query in "${inputs[@]}"; do
    echo "${query}"
  done | python "scripts/nlp/punctuation_client.py" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  output_detector="Enter a query: Inference complete in "
  num_outputs="$(grep -P "${output_detector}" "${stdout_file}" | wc -l)"
  if [[ "${num_outputs}" != "${#inputs[@]}" ]]; then
    echo "FAILED: expected ${#inputs[@]} outputs whereas ${num_outputs} were found. Outputs are detected by "\
"'${output_detector}' regexp. See full outputs in ${stdout_file} file."
    exit 1
  fi
  for i in "${!expected_outputs[@]}"; do
    found="$(grep -F "${expected_outputs[$i]}" "${stdout_file}" | wc -l)"
    if ((found < 1)); then
      echo "FAILED: expected output '${expected_outputs[$i]}' for ${i} query is not found. See full output in "\
"file ${stdout_file}."
      exit 1
    fi
  done
}

test_interactive

function test_run_tests(){
  exp_options="--run-tests"
  echo "  options: ${exp_options}"
  success_string="Tests passed: 4"
  success="$(python "scripts/nlp/punctuation_client.py" ${server_args} ${exp_options} 2>"${stderr_file}" \
    | tee "${stdout_file}" \
    | grep -F "${success_string}" | wc -l)"
  if ((success < 1)); then
    echo "FAILED: a string '${success_string}' indicating that test is successful is not found. "\
"See all output in ${stdout_file}"
    exit 1
  fi
}

# Doesn't work on windows because of Korean characters.
if [[ "${OSTYPE}" != msys ]] && [[ "${OSTYPE}" != win32 ]]; then
  test_run_tests
fi

set +e