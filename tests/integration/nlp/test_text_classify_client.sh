set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/../helpers.sh"
source "$(dirname $0)/test_functions.sh"

test_output_dir="$(dirname $0)/outputs/test_text_classify_client"
mkdir -p "${test_output_dir}"
rm -rf "${test_output_dir}"/*

test_for_specific_string text_classify_client.py "(['meteorology'], ["

set +e