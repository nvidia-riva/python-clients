set -e
source "$(dirname $0)/export_server_vars.sh"

echo "Testing script talk.py"
bash "$(dirname $0)/tts/test_talk.sh"

set +e