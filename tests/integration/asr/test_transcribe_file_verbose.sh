set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/init_server_cli_params.sh"
source "$(dirname $0)/test_functions.sh"

test_output_dir="$(dirname $0)/outputs/test_transcribe_file_verbose"


function test_verbose_format(){
  mkdir -p "${test_output_dir}"
  rm -rf "${test_output_dir}"/*
  input_file="en-US_sample.wav"
  exp_options="--input-file examples/${input_file}"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_verbose_format.txt"
  stderr_file="${test_output_dir}/stderr_verbose_format.txt"
  set +e
  python "scripts/asr/transcribe_file_verbose.py" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  number_of_stability_messages="$(grep "Stability:" "${stdout_file}" | wc -l)"
  number_of_confidence_messages="$(grep "Confidence:" "${stdout_file}" | wc -l)"
  if ((number_of_stability_messages < 1 || number_of_confidence_messages < 1)); then
    echo "FAILED. Verbose format is wrong. Expected at least 1 stability message and at least 1 confidence message, "\
"whereas ${number_of_stability_messages} stability messages found and ${number_of_confidence_messages} confidence "\
"messages found. See ${stdout_file}."
    exit 1
  fi
}


test_verbose_format
test_language_code transcribe_file_verbose.py
test_transcript_affecting_params transcribe_file_verbose.py
set +e
