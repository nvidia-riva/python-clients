set -e
source "$(dirname $0)/init_server_cli_params.sh"
source "$(dirname $0)/test_functions.sh"



test_simulate_realtime transcribe_file.py
test_language_code transcribe_file.py
test_transcript_affecting_params transcribe_file.py

set +e