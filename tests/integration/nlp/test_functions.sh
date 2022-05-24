function test_for_specific_string(){
  script_name="$1"
  expected_string="$2"
  exp_options=""
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout.txt"
  stderr_file="${test_output_dir}/stderr.txt"
  set +e
  python "scripts/nlp/${script_name}" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  found_result="$(grep -F "${expected_string}" "${stdout_file}" | wc -l)"
  if ((found_result < 1)); then
    echo "FAILED: no results were found in standard output. "\
"Results were searched by string '${expected_string}'. Standard output in file ${stdout_file}"
    exit 1
  fi
}