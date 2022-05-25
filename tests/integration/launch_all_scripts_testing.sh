set -e
source "$(dirname $0)/export_server_vars.sh"

echo "TESTING TTS SCRIPTS..."
bash "$(dirname $0)/tts.sh"

echo "TESTING NLP SCRIPTS..."
bash "$(dirname $0)/nlp.sh"

echo "TESTING ASR SCRIPTS..."
bash "$(dirname $0)/asr.sh"

set +e