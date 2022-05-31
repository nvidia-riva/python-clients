# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e
source "$(dirname $0)/export_server_vars.sh"

echo "TESTING TTS SCRIPTS..."
bash "$(dirname $0)/tts.sh"

echo "TESTING NLP SCRIPTS..."
bash "$(dirname $0)/nlp.sh"

echo "TESTING ASR SCRIPTS..."
bash "$(dirname $0)/asr.sh"

set +e