set -e
source "$(dirname $0)/export_server_vars.sh"

echo "Testing script intentslot_client.py"
bash "$(dirname $0)/nlp/test_intentslot_client.sh"

set +e