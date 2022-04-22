set -x -e
python clients/asr/riva_streaming_asr_client.py --input-file examples/en-US_sample.wav
asr_outputs=tests/asr_outputs
asr_expected_outputs=tests/asr_expected_outputs
mkdir -p "${asr_outputs}"
new_output="${asr_outputs}/riva_streaming_asr_client_en-US.txt"
mv output_0.txt "${new_output}"
expected_output="${asr_expected_outputs}/riva_streaming_asr_client_en-US.txt"
line_number=0
while read file1_line <&3 && read file2_line <&4; do
  if [[ "${file1_line#*s:}" != "${file2_line#*s:}" ]] ; then
    printf "Output of \`riva-streaming_asr_client.py\` is not identical to expected output for line ${line_number}."
    exit 1
  fi
done 3<"${new_output}" 4<"${expected_output}"


#new_output="${asr_outputs}/transcribe_file_en-US.txt"
#python clients/asr/transcribe_file.py --audio-file examples/en-US_sample.wav > "${new_output}"
#expected_output="${asr_expected_outputs}/transcribe_file_en-US.txt"
#if cmp -s "${new_output}" "${expected_output}"; then
#    printf 'OK transcribe_file.py'
#else
#    printf 'Output of `transcribe_file.py` is not identical to expected output.'
#    diff "${new_output}" "${expected_output}"
#    exit 1
#fi


new_output="${asr_outputs}/transcribe_file_offline_en-US.txt"
python clients/asr/transcribe_file_offline.py --audio-file examples/en-US_sample.wav > "${new_output}"
expected_output="${asr_expected_outputs}/transcribe_file_offline_en-US.txt"
if cmp -s "${new_output}" "${expected_output}"; then
    printf 'OK transcribe_file_offline.py'
else
    printf 'Output of `transcribe_file_offline.py` is not identical to expected output.'
    diff "${new_output}" "${expected_output}"
    exit 1
fi


new_output="${asr_outputs}/transcribe_file_rt_en-US.txt"
python clients/asr/transcribe_file_rt.py --audio-file examples/en-US_sample.wav > "${new_output}"
expected_output="${asr_expected_outputs}/transcribe_file_rt_en-US.txt"
if cmp -s "${new_output}" "${expected_output}"; then
    printf 'OK transcribe_file_rt.py'
else
    printf 'Output of `transcribe_file_rt.py` is not identical to expected output.'
    diff "${new_output}" "${expected_output}"
    exit 1
fi


new_output="${asr_outputs}/transcribe_file_verbose_en-US.txt"
python clients/asr/transcribe_file_verbose.py --audio-file examples/en-US_sample.wav > "${new_output}"
expected_output="${asr_expected_outputs}/transcribe_file_verbose_en-US.txt"
if cmp -s "${new_output}" "${expected_output}"; then
    printf 'OK transcribe_file_verbose.py'
else
    printf 'Output of `transcribe_file_verbose.py` is not identical to expected output.'
    diff "${new_output}" "${expected_output}"
    exit 1
fi


set +x +e