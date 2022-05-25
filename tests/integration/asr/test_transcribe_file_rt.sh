set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/../test_functions.sh"
source "$(dirname $0)/test_functions.sh"

source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)" "transcribe_file_rt.py"

test_list_devices asr/transcribe_file_rt.py Output
test_string_presence \
  transcribe_file_rt.py \
  "--input-file examples/en-US_sample.wav --language-code ru-RU" \
  "details = \"Error: Model is not available on server\"" \
  language_code_ru_RU \
  1
test_transcript_affecting_params transcribe_file_rt.py
set +e