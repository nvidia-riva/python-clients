set -x
python clients/asr/riva_streaming_asr_client.py --input-file examples/en-US_sample.wav
mkdir -p tests/asr_outputs
mv output_0.txt tests/asr_outputs/riva_streaming_asr_client_en-US.txt
new_output=tests/asr_outputs/riva_streaming_asr_client_en-US.txt
expected_output=tests/asr_expected_outputs/riva_streaming_asr_client_en-US.txt
if cmp -s "${new_output}" "${expected_output}"; then
    printf 'OK riva_streaming_asr_client.py'
else
    printf 'Output of `riva-streaming_asr_client.py` is not identical to expected output.'
    diff "${new_output}" "${expected_output}"
    exit 1
fi


new_output=tests/transcribe_file_en-US.txt
python clients/asr/transcribe_file.py --audio-file examples/en-US_sample.wav > "${new_output}"
expected_output=tests/transcribe_file_en-US.txt
if cmp -s "${new_output}" "${expected_output}"; then
    printf 'OK transcribe_file.py'
else
    printf 'Output of `transcribe_file.py` is not identical to expected output.'
    diff "${new_output}" "${expected_output}"
    exit 1
fi


new_output=tests/transcribe_file_offline_en-US.txt
python clients/asr/transcribe_file_offline.py --audio-file examples/en-US_sample.wav > "${new_output}"
expected_output=tests/transcribe_file_offline_en-US.txt
if cmp -s "${new_output}" "${expected_output}"; then
    printf 'OK transcribe_file_offline.py'
else
    printf 'Output of `transcribe_file_offline.py` is not identical to expected output.'
    diff "${new_output}" "${expected_output}"
    exit 1
fi


new_output=tests/transcribe_file_rt_en-US.txt
python clients/asr/transcribe_file_rt.py --audio-file examples/en-US_sample.wav > "${new_output}"
expected_output=tests/transcribe_file_rt_en-US.txt
if cmp -s "${new_output}" "${expected_output}"; then
    printf 'OK transcribe_file_rt.py'
else
    printf 'Output of `transcribe_file_rt.py` is not identical to expected output.'
    diff "${new_output}" "${expected_output}"
    exit 1
fi


new_output=tests/transcribe_file_verbose_en-US.txt
python clients/asr/transcribe_file_verbose.py --audio-file examples/en-US_sample.wav > "${new_output}"
expected_output=tests/transcribe_file_verbose_en-US.txt
if cmp -s "${new_output}" "${expected_output}"; then
    printf 'OK transcribe_file_verbose.py'
else
    printf 'Output of `transcribe_file_verbose.py` is not identical to expected output.'
    diff "${new_output}" "${expected_output}"
    exit 1
fi


set +x