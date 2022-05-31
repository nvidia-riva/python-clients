# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e
source "$(dirname $0)/../export_server_vars.sh"
source "$(dirname $0)/../init_server_cli_params.sh"
source "$(dirname $0)/../helpers.sh"
source "$(dirname $0)/test_functions.sh"

source "$(dirname $0)/../prepare_test_output_dir.sh" "$(dirname $0)" "intentslot_client.py"


test_error_is_raised intentslot_client.py "--model foo" \
  "Error: Model foo is not a Riva API model, execution cannot be done" \
  "wrong_model"


function test_not_interactive(){
  exp_options=""
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_not_interactive.txt"
  stderr_file="${test_output_dir}/stderr_not_interactive.txt"
  set +e
  python "scripts/nlp/intentslot_client.py" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"
  retVal=$?
  process_exit_status
  target_intent="weather.weather"
  target_slots="['weatherforecastdaily', 'weatherplace']"
  target_slot_tokens="['tomorrow', '?']"
  found_target_intent="$(grep -F "${target_intent}" "${stdout_file}" | wc -l)"
  found_target_slots="$(grep -F "${target_slots}" "${stdout_file}" | wc -l)"
  found_target_slot_tokens="$(grep -F "${target_slot_tokens}" "${stdout_file}" | wc -l)"
  if ((found_target_intent < 1 || found_target_slots < 1 || found_target_slot_tokens < 1)); then
    msg="FAILED. Target"
    not_found=0
    if ((found_target_intent < 1)); then
      msg="${msg} intent '${target_intent}'"
      not_found=1
    fi
    if ((found_target_slots < 1)); then
      if ((not_found > 0)); then
        msg="${msg},"
      fi
      msg="${msg} slots \"${target_slots}\""
      not_found=1
    fi
    if ((found_target_slot_tokens < 1)); then
      if ((not_found > 0)); then
        msg="${msg},"
      fi
      msg="${msg} slot tokens \"${target_slot_tokens}\""
    fi
    msg="${msg} are not found. See actual output in stdout file ${stdout_file}."
    echo "${msg}"
    exit 1
  fi
}

test_not_interactive


function test_grep_vs_file(){
  pattern=$1
  entity_name=$2
  stdout_file_=$3
  arr=("$@")
  arr=("${arr[@]:3}")
  num=0
  while read -r line ; do
    pred="${line#"${pattern}"}"
    pred="$(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' <<<"${pred}")"
    if [[ "${arr["${num}"]}" != "${pred}" ]]; then
      >&2 echo "FAILED: detected ${entity_name} \"${pred}\" for ${num} query does not match expected ${entity_name} "\
"\"${arr["${num}"]}\". See all outputs in ${stdout_file_}."
      exit 1
    fi
    ((num++))
  done < <(grep -F "${pattern}" "${stdout_file_}")
  echo "${num}"
}


function test_number(){
  tested_number=$1
  entity_name=$2
  stdout_file_=$3
  correct_number=$4
  if [[ "${tested_number}" != "${correct_number}" ]]; then
    echo "FAILED: number of found ${entity_name} is ${num_found_intents} whereas "\
"${correct_number} is expected. See all outputs in ${stdout_file_}."
    exit 1
  fi
}


function test_interactive(){
  inputs=(
    "What is the weather tomorrow?"
    "Tel me the weather in LA."
  )
  expected_intents=(
    "weather.weather"
    "weather.weather"
  )
  expected_slots=(
    "['weatherforecastdaily', 'weatherplace']"
    "['weatherplace', 'weathertime']"
  )
  expected_slot_tokens=(
    "tomorrow(weatherforecastdaily) ?(weatherplace)"
    "la(weatherplace) .(weathertime)"
  )
  exp_options="--interactive"
  echo "  options: ${exp_options}"
  stdout_file="${test_output_dir}/stdout_interactive.txt"
  stderr_file="${test_output_dir}/stderr_interactive.txt"
  set +e
  for query in "${inputs[@]}"; do
    echo "${query}"
  done | python "scripts/nlp/intentslot_client.py" ${server_args} ${exp_options} \
    1>"${stdout_file}" 2>"${stderr_file}"

  num_found_intents="$(test_grep_vs_file "Intent: " "intent" "${stdout_file}" "${expected_intents[@]}")"
  retVal=$?
  if [[ $retVal != 0 ]]; then exit $retVal; fi

  num_found_slots="$(test_grep_vs_file "Slots: " "slots" "${stdout_file}" "${expected_slots[@]}")"
  retVal=$?
  if [[ $retVal != 0 ]]; then exit $retVal; fi

  num_found_slot_tokens="$(test_grep_vs_file "Combined: " "slot tokens" "${stdout_file}" "${expected_slot_tokens[@]}")"
  retVal=$?
  if [[ $retVal != 0 ]]; then exit $retVal; fi

  test_number "${num_found_intents}" "intents" "${stdout_file}" "${#expected_intents[@]}"
  test_number "${num_found_slots}" "slots records" "${stdout_file}" "${#expected_slots[@]}"
  test_number "${num_found_slot_tokens}" "slot tokens records" "${stdout_file}" "${#expected_slot_tokens[@]}"
}

test_interactive

set +e