# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

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
  for i in "${!options[@]}"; do
    if [[ "${test_max_alternatives}" == 0 ]] && [[ "${options[$i]}" == *"--max-alternatives"* ]]; then
      continue
    fi
    exp_options="--input-file data/examples/${input_files[$i]} ${options[$i]}"
    echo "  options: ${exp_options}"
    stdout_file="${test_output_dir}/stdout_options_${i}.txt"
    stderr_file="${test_output_dir}/stderr_options_${i}.txt"
    set +e
    python "scripts/asr/${script_name}" ${server_args} ${exp_options} \
      1>"${stdout_file}" 2>"${stderr_file}"
    retVal=$?
    process_exit_status
    if [[ "${use_stdout_for_testing}" == 1 ]]; then
      output_test_file="${stdout_file}"
    else
      output_test_file="${test_output_dir}/output_0_options_${i}.txt"
      mv output_0.txt "${output_test_file}"
    fi
    if [[ "${offline}" == 1 ]]; then
      transcript_line="$(tac "${output_test_file}" | grep -F -m 1 'Final transcript:')"
      predicted_transcript="${transcript_line#Final transcript: }"
    else
      if [[ "${time_info_before_final_transcript}" == 1 ]]; then
        transcript_line="$(tac "${output_test_file}" | grep -F -m 1 'Transcript 0:')"
        predicted_transcript="${transcript_line#*Transcript *: }"
      else
        transcript_line="$(tac "${output_test_file}" | grep -F -m 1 '## ')"
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
  input_file="en-US_AntiBERTa_for_word_boosting_testing.wav"
  input_file_length_seconds=14
  exp_options="--input-file data/examples/${input_file} --simulate-realtime"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_simulate_realtime.txt"
  stderr_file="${test_output_dir}/stderr_simulate_realtime.txt"
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


function test_string_presence(){
  script_name="$1"
  exp_options="$2"
  expected_string="$3"
  test_name="$4"
  stderr="$5"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_${test_name}.txt"
  stderr_file="${test_output_dir}/stderr_${test_name}.txt"
  set +e
  python "scripts/asr/${script_name}" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  if [[ "${stderr}" == 1 ]]; then
    set -e
  else
    process_exit_status
  fi
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
