set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/test_functions.sh"

test_list_devices transcribe_file_rt.py Output
test_language_code transcribe_file_rt.py
test_transcript_affecting_params transcribe_file_rt.py
set +e