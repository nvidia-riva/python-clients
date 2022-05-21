set -e
source "$(dirname $0)/export_server_vars.sh"
echo "TESTING ASR SCRIPTS..."
bash "$(dirname $0)/asr.sh"
set +e