set -e
source "$(dirname $0)/export_server_vars.sh"

echo "Testing script eval_intent_slot.py"
bash "$(dirname $0)/nlp/test_eval_intent_slot.sh"

echo "Testing script classify_client.py"
bash "$(dirname $0)/nlp/test_text_classify_client.sh"

echo "Testing script qa_client.py"
bash "$(dirname $0)/nlp/test_qa_client.sh"

echo "Testing script punctuation_client.py"
bash "$(dirname $0)/nlp/test_punctuation_client.sh"

echo "Testing script ner_client.py"
bash "$(dirname $0)/nlp/test_ner_client.sh"

echo "Testing script intentslot_client.py"
bash "$(dirname $0)/nlp/test_intentslot_client.sh"

set +e