set -e
source "$(dirname $0)/init_server_cli_params.sh"

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

expected_final_transcripts=(
  "what is natural language processing"
  "What is natural language processing?"
  "what is natural language processing"
  "35 % of 40 equals 14"
  "AntiBERTa and ABlooper both transformer based language models are examples "\
"of the emerging work in using graph networks to design protein sequences for "\
"particular target antigens"
)

test_output_dir="$(dirname $0)/outputs/test_riva_streaming_asr_client"
reference_outputs="$(dirname $0)/reference_outputs/test_riva_streaming_asr_client"
mkdir -p "${test_output_dir}"
rm -rf "${test_output_dir}"/*

rm -f output_0.txt


function process_exit_status(){
  set -e
  if [ "${retVal}" -ne 0 ]; then
    echo "Command failed with non zero exit status ${retVal}. "\
"See errors in ${stderr_file} and standard output ${stdout_file}"
    echo "stderr:"
    cat "${stderr_file}"
    exit "${retVal}"
  fi
}


for i in "${!options[@]}"; do
  exp_options="--input-file examples/${input_files[$i]} ${options[$i]}"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_options_${i}.txt"
  stderr_file="${test_output_dir}/stderr_options_${i}.txt"
  set +e
  python scripts/asr/riva_streaming_asr_client.py ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  new_file_name="${test_output_dir}/output_0_options_${i}.txt"
  mv output_0.txt "${new_file_name}"
  last_line="$(awk '/./{line=$0} END{print line}' "${new_file_name}")"
  predicted_transcript="${last_line#*Transcript *: }"
  # strip spaces
  predicted_transcript="$(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'<<<"${predicted_transcript}")"
  if [[ "${predicted_transcript}" != "${expected_final_transcripts[$i]}" ]]; then
    echo "FAILED on set of options number ${i}. Predicted transcript: '${predicted_transcript}'. "\
"Expected transcript: '${expected_final_transcripts[$i]}'."
    exit 1
  fi
done

# Testing --word-time-offsets
input_file="en-US_AntiBERTa_for_word_boosting_testing.wav"
exp_options="--input-file examples/${input_file} --word-time-offsets "\
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

# Testing --language-code
input_file="en-US_sample.wav"
exp_options="--input-file examples/${input_file} --language-code ru-RU"
echo "  options: ${exp_options}"
stdout_file="${test_output_dir}/stdout_language_code_ru_RU.txt"
stderr_file="${test_output_dir}/stderr_language_code_ru_RU.txt"
set +e
python scripts/asr/riva_streaming_asr_client.py ${server_args} ${exp_options} \
  1>"${stdout_file}" 2>"${stderr_file}"
retVal=$?
set -e
error_string="details = \"Error: Model is not available on server\""
if [ -z "$(grep "${error_string}" "${stderr_file}")" ]; then
  echo "A grpc error is expected if --language-code=ru-RU because such models are not available on server. "\
"A string '${error_string}' is not found in file ${stderr_file}"
  exit 1
fi
set +e

# Testing --num-clients
rm output_*.txt
input_file="en-US_sample.wav"
exp_options="--input-file examples/${input_file} --num-clients 2"
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

# Testing --num-iterations
num_iterations=2
input_file="en-US_sample.wav"
exp_options="--input-file examples/${input_file} --num-iterations ${num_iterations}"
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
num_final_transcripts="$(grep "Transcript 0:" "${new_file_name}" | wc -l)"
if ((num_final_transcripts != num_iterations)); then
  echo "FAILED. Number of final transcripts has to be ${num_iterations} if "\
"--num-iterations=${num_iterations}, whereas number "\
"of final transcripts is ${num_final_transcripts}."
fi

# Testing --simulate-realtime
input_file="en-US_AntiBERTa_for_word_boosting_testing.wav"
input_file_length_seconds=14
exp_options="--input-file examples/${input_file} --simulate-realtime"
echo "  options: ${exp_options}"
stdout_file="${test_output_dir}/stdout_simulate_realtime.txt"
stderr_file="${test_output_dir}/stderr_simulate_realtime.txt"
start_time=$(date +%s)
set +e
python scripts/asr/riva_streaming_asr_client.py ${server_args} ${exp_options} \
  1>"${stdout_file}" 2>"${stderr_file}"
retVal=$?
process_exit_status
end_time=$(date +%s)
elapsed=$(( end_time - start_time ))
new_file_name="${test_output_dir}/output_0_simulate_realtime.txt"
mv output_0.txt "${new_file_name}"
if ((elapsed < input_file_length_seconds)); then
  echo "FAILED. When option --simulate-realtime is provided, time spent on audio processing has to greater "\
"or equal than audio length. Audio length: ${input_file_length_seconds}s. Time spent: ${elapsed}s."
fi
