test_output_dir_="$1/outputs/test_${script_name%.*}"
mkdir -p "${test_output_dir_}"
rm -rf "${test_output_dir_}"/*