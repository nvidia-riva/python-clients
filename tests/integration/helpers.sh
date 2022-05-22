function process_exit_status(){
  set -e
  if [ "${retVal}" -ne 0 ]; then
    echo "Command failed with non zero exit status ${retVal}. "\
"See errors in ${stderr_file} and standard output ${stdout_file}"
    echo "stderr:"
    cat "${stderr_file}"
    exit "${retVal}"
  fi
}