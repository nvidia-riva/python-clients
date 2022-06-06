# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/test_functions.sh"


reference_outputs="$(dirname $0)/reference_outputs/test_riva_streaming_asr_client"
source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)" "riva_streaming_asr_client.py"

rm -f output_0.txt

test_string_presence \
  riva_streaming_asr_client.py \
  "--input-file data/examples/en-US_sample.wav --language-code ru-RU" \
  "details = \"Error: Unavailable model requested. Lang: ru-RU, Type: online\"" \
  language_code_ru_RU \
  1
test_simulate_realtime riva_streaming_asr_client.py
test_transcript_affecting_params riva_streaming_asr_client.py

# Testing --word-time-offsets
function test_word_time_offsets(){
  input_file="en-US_AntiBERTa_for_word_boosting_testing.wav"
  exp_options="--input-file data/examples/${input_file} --word-time-offsets "\
"--boosted-lm-words AntiBERTa --boosted-lm-words ABlooper --boosted-lm-score 20.0"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_word_time_offsets.txt"
  stderr_file="${test_output_dir}/stderr_word_time_offsets.txt"
  set +e
  python scripts/asr/riva_streaming_asr_client.py ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  new_file_name="${test_output_dir}/output_0_word_time_offsets.txt"
  mv output_0.txt "${new_file_name}"
  total_lines="$(wc -l "${new_file_name}" | cut -d ' ' -f1)"
  timestamps_start_line="$(awk '/Timestamps:/{print NR}' "${new_file_name}")"
  line_i=1
  reference_file="${reference_outputs}/time_stamps_AntiBERTa.txt"
  while read hyp_line <&3 && read ref_line <&4; do
    ref_line="$(echo "${ref_line}" | tr -d '\n\r')"
    if [[ "${hyp_line}" != "${ref_line}" ]]; then
      echo "${line_i}th line time stamps outputs do not match reference."
      echo "hypothesis: '${hyp_line}'"
      echo "reference:  '${ref_line}'"
      exit 1
    fi
    ((line_i++))
  done 3< <(sed -n "${timestamps_start_line},${total_lines}p" "${new_file_name}") 4<"${reference_file}"
  num_reference_lines="$(wc -l "${reference_file}" | cut -d ' ' -f1)"
  if (( num_reference_lines != line_i - 1 )); then
    echo "Number of lines in reference file ${reference_file} is ${num_reference_lines} whereas $((line_i - 1)) "\
"timestamp lines in output file ${new_file_name} were found."
    exit 1
  fi
  if (( line_i - 1 != total_lines - timestamps_start_line + 1 )); then
    echo "Number of hypothesis timestamp lines from file ${new_file_name} is "\
"$((total_lines - timestamps_start_line + 1)) whereas only $((line_i - 1)) "\
"lines are present in reference file ${reference_file}."
  fi
}

test_word_time_offsets

# Testing --num-clients
function test_num_clients(){
  rm -f output_*.txt
  input_file="en-US_sample.wav"
  exp_options="--input-file data/examples/${input_file} --num-clients 2"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_num_clients_2.txt"
  stderr_file="${test_output_dir}/stderr_num_clients_2.txt"
  set +e
  python scripts/asr/riva_streaming_asr_client.py ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  num_output_files="$(find . -maxdepth 1 -name "output_*.txt" | wc -l)"
  if [[ "${num_output_files}" != 2 ]]; then
    echo "If number of output files has to be 2 whereas ${num_output_files} matching output_*.txt were found."
    exit 1
  else
    if [ ! -f output_0.txt ]; then
      echo "Output file output_0.txt is not found"
      exit 1
    else
      if [ ! -f output_1.txt ]; then
        echo "Output file output_1.txt is not found"
        exit 1
      fi
    fi
  fi
  new_file_name="${test_output_dir}/output_0_num_clients_2.txt"
  mv output_0.txt "${new_file_name}"
  new_file_name_1="${test_output_dir}/output_1_num_clients_2.txt"
  mv output_1.txt "${new_file_name_1}"
}

test_num_clients

function test_num_iterations(){
  num_iterations=2
  input_file="en-US_sample.wav"
  exp_options="--input-file data/examples/${input_file} --num-iterations ${num_iterations}"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_num_iterations.txt"
  stderr_file="${test_output_dir}/stderr_num_iterations.txt"
  set +e
  python scripts/asr/riva_streaming_asr_client.py ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  new_file_name="${test_output_dir}/output_0_num_iterations.txt"
  mv output_0.txt "${new_file_name}"
  num_final_transcripts="$(grep -F "Transcript 0:" "${new_file_name}" | wc -l)"
  if ((num_final_transcripts != num_iterations)); then
    echo "FAILED. Number of final transcripts has to be ${num_iterations} if "\
"--num-iterations=${num_iterations}, whereas number "\
"of final transcripts is ${num_final_transcripts}."
  fi
}

test_num_iterations
