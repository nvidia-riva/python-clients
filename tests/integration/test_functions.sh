# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

source "$(dirname $0)/../helpers.sh"


function test_list_devices(){
  script_name="$1"
  prefix="$2"
  exp_options="--list-devices"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_list_devices.txt"
  stderr_file="${test_output_dir}/stderr_list_devices.txt"
  set +e
  python "scripts/${script_name}" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  list_header="${prefix} audio devices:"
  list_header_found="$(grep -F "${list_header}" "${stdout_file}" | wc -l)"
  if ((list_header_found < 1)); then
    echo "FAILED: a header '${list_header}' of devices list is not found in standard output. "\
"See stdout in file '${stdout_file}'."
    exit 1
  fi
}
