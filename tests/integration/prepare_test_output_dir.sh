script_name_="$2"
test_output_dir="$1/outputs/test_${script_name_%.*}"
mkdir -p "${test_output_dir}"
rm -rf "${test_output_dir}"/*