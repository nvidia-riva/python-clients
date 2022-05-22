source "$(dirname $0)/../helpers.sh"


function test_transcript_affecting_params(){
  script_name="$1"
  source "$(dirname $0)/define_test_control_vars.sh"
  input_files=(
    "en-US_sample.wav"
    "en-US_sample.wav"
    "en-US_sample.wav"
    "en-US_percent.wav"
    "en-US_AntiBERTa_for_word_boosting_testing.wav"
  )

  options=(
    ""
    "--automatic-punctuation"
    "--max-alternatives 2"
    "--no-verbatim-transcripts"
    "--boosted-lm-words AntiBERTa --boosted-lm-words ABlooper --boosted-lm-score 20.0"
  )

  expected_final_streaming_transcripts=(
    "what is natural language processing"
    "What is natural language processing?"
    "what is natural language processing"
    "35 % of 40 equals 14"
    "AntiBERTa and ABlooper both transformer based language models are examples "\
"of the emerging work in using graph networks to design protein sequences for "\
"particular target antigens"
  )
  expected_final_offline_transcripts=("${expected_final_streaming_transcripts[@]}")
  expected_final_offline_transcripts[3]="hello 35 % of 40 equals 14"
  source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)"
  for i in "${!options[@]}"; do
    if [[ "${test_max_alternatives}" == 0 ]] && [[ "${options[$i]}" == *"--max-alternatives"* ]]; then
      continue
    fi
    exp_options="--input-file examples/${input_files[$i]} ${options[$i]}"
    echo "  options: ${exp_options}"
    stdout_file="${test_output_dir_}/stdout_options_${i}.txt"
    stderr_file="${test_output_dir_}/stderr_options_${i}.txt"
    set +e
    python "scripts/asr/${script_name}" ${server_args} ${exp_options} \
      1>"${stdout_file}" 2>"${stderr_file}"
    retVal=$?
    process_exit_status
    if [[ "${use_stdout_for_testing}" == 1 ]]; then
      output_test_file="${stdout_file}"
    else
      output_test_file="${test_output_dir_}/output_0_options_${i}.txt"
      mv output_0.txt "${output_test_file}"
    fi
    if [[ "${offline}" == 1 ]]; then
      transcript_line="$(tac "${output_test_file}" | grep -m 1 'Final transcript:')"
      predicted_transcript="${transcript_line#Final transcript: }"
    else
      if [[ "${time_info_before_final_transcript}" == 1 ]]; then
        transcript_line="$(tac "${output_test_file}" | grep -m 1 'Transcript 0:')"
        predicted_transcript="${transcript_line#*Transcript *: }"
      else
        transcript_line="$(tac "${output_test_file}" | grep -m 1 '## ')"
        predicted_transcript="${transcript_line#*## }"
      fi
    fi
    # strip spaces
    predicted_transcript="$(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'<<<"${predicted_transcript}")"
    if [[ "${offline}" == 1 ]]; then
      expected_final_transcript="${expected_final_offline_transcripts[$i]}"
    else
      expected_final_transcript="${expected_final_streaming_transcripts[$i]}"
    fi
    if [[ "${predicted_transcript}" != "${expected_final_transcript}" ]]; then
      echo "FAILED on set of options number ${i}. Predicted transcript: '${predicted_transcript}'. "\
"Expected transcript: '${expected_final_transcript}'."
      exit 1
    fi
  done
}


function test_simulate_realtime(){
  script_name="$1"
  source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)"
  input_file="en-US_AntiBERTa_for_word_boosting_testing.wav"
  input_file_length_seconds=14
  exp_options="--input-file examples/${input_file} --simulate-realtime"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir_}/stdout_simulate_realtime.txt"
  stderr_file="${test_output_dir_}/stderr_simulate_realtime.txt"
  start_time=$(date +%s)
  set +e
  python "scripts/asr/${script_name}" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  end_time=$(date +%s)
  elapsed=$(( end_time - start_time ))
  if ((elapsed < input_file_length_seconds)); then
    echo "FAILED. When option --simulate-realtime is provided, time spent on audio processing has to greater "\
  "or equal than audio length. Audio length: ${input_file_length_seconds}s. Time spent: ${elapsed}s."
    exit 1
  fi
}


function test_language_code(){
  script_name="$1"
  source "$(dirname $0)/define_test_control_vars.sh"
  source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)"
  input_file="en-US_sample.wav"
  exp_options="--input-file examples/${input_file} --language-code ru-RU"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir_}/stdout_language_code_ru_RU.txt"
  stderr_file="${test_output_dir_}/stderr_language_code_ru_RU.txt"
  set +e
  python "scripts/asr/${script_name}" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  set -e
  if [[ "${offline}" == 1 ]]; then
    error_string="Error: Model is not available on server"
    check_file="${stdout_file}"
  else
    error_string="details = \"Error: Model is not available on server\""
    check_file="${stderr_file}"
  fi
  if [ -z "$(grep "${error_string}" "${check_file}")" ]; then
    echo "A grpc error is expected if --language-code=ru-RU because such models are not available on server. "\
"A string '${error_string}' is not found in file ${stderr_file}"
    exit 1
  fi
  set +e
}


function test_list_devices(){
  script_name="$1"
  prefix="$2"
  source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)"
  exp_options="--list-devices"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir_}/stdout_list_devices.txt"
  stderr_file="${test_output_dir_}/stderr_list_devices.txt"
  set +e
  python "scripts/asr/${script_name}" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  list_header="${prefix} audio devices:"
  list_header_found="$(grep "${list_header}" "${stdout_file}" | wc -l)"
  if ((list_header_found < 1)); then
    echo "FAILED: a header '${list_header}' of devices list is not found in standard output. "\
"See stdout in file '${stdout_file}'."
    exit 1
  fi
  set +e
}