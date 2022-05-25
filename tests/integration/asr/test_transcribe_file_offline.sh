set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/test_functions.sh"

source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)" "transcribe_file_offline.py"

test_language_code transcribe_file_offline.py
test_transcript_affecting_params transcribe_file_offline.py
set +e