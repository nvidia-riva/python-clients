set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/init_server_cli_params.sh"
source "$(dirname $0)/test_functions.sh"

test_output_dir="$(dirname $0)/outputs/test_transcribe_file"

function test_show_intermediate(){
  input_file="en-US_sample.wav"
  exp_options="--input-file examples/${input_file} --show-intermediate"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_show_intermediate.txt"
  stderr_file="${test_output_dir}/stderr_show_intermediate.txt"
  set +e
  python "scripts/asr/transcribe_file.py" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  number_of_intermediate_prints="$(grep ">>" "${stdout_file}" | wc -l)"
  if ((number_of_intermediate_prints < 1)); then
    echo "FAILED. When option --show-intermediate is provided, there has to be at least 1 intermediate print "\
"whereas no intermediate prints were found. Intermediate prints start with '>>'. See ${stdout_file}."
    exit 1
  fi
}

test_show_intermediate
test_simulate_realtime transcribe_file.py
test_language_code transcribe_file.py
test_transcript_affecting_params transcribe_file.py

set +e