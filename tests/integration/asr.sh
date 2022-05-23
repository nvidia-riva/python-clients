set -e
source "$(dirname $0)/export_server_vars.sh"

echo "Testing script transcribe_mic.py"
bash "$(dirname $0)/asr/test_transcribe_mic.sh"
echo "Testing script transcribe_file_rt.py"
bash "$(dirname $0)/asr/test_transcribe_file_rt.sh"
echo "Testing script riva_streaming_asr_client.py ..."
bash "$(dirname $0)/asr/test_riva_streaming_asr_client.sh"
echo "Testing script transcribe_file_offline.py"
bash "$(dirname $0)/asr/test_transcribe_file_offline.sh"
echo "Testing script transcribe_file.py ..."
bash "$(dirname $0)/asr/test_transcribe_file.sh"
echo "Testing script transcribe_file_verbose.py"
bash "$(dirname $0)/asr/test_transcribe_file_verbose.sh"

set +e