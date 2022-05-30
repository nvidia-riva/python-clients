#!/usr/bin/env python
import argparse
import csv
import itertools
import os.path
import warnings
from pathlib import Path
from typing import Dict, List, NewType, Optional, Tuple, Union

from sklearn.metrics import classification_report
from sklearn.preprocessing import LabelEncoder
from transformers import BertTokenizer, PreTrainedTokenizerBase

import riva_api
from riva_api.argparse_utils import add_connection_argparse_parameters


def combine_subwords(tokens):
    """This function combines subwords into single word

  Parameters
  ----------
  line : list
      input tokens generated using BERT tokenizer which may have subwords
      separated by "##".

  Returns
  -------
  list:
      a list of combined subwords token
  """
    combine_tokens = []
    total_tokens = len(tokens)
    idx = 0

    while idx < total_tokens:
        ct = tokens[idx]
        token = ""
        if ct.startswith("##"):
            # remove last token as it needs to be combine with current token
            token += combine_tokens.pop(-1)
            token += ct.strip("##")
            idx += 1
            while idx < total_tokens:
                ct = tokens[idx]
                if ct.startswith("##"):
                    token += ct.strip("##")
                else:
                    idx = idx - 1  # put back the token
                    break
                idx += 1
        else:
            token = ct
        combine_tokens.append(token)
        idx += 1

    # print("combine_tokens=", combine_tokens)
    return combine_tokens


SlotsType = NewType('SlotsType', List[Dict[str, Union[int, str]]])


def read_tsv_file(input_file: Union[str, os.PathLike]) -> List[Dict[str, Union[str, SlotsType]]]:
    """
    Reads .tsv file ``input_file`` with test data in format
    ```
    <intent_name>TAB<start_char_idx>:<end_char_idx>:<slot_name>,<start_char_idx>:<end_char_idx>:<slot_name>TAB<query>
    ```
    :param input_file: a path to input file
    :return: a list of examples for testing. Each example has format:
        ```
        {
            "intent": <intent_name>,
            "slots": {
                 "start": <start_character_ind>,
                 "end": <end_character_ind>,
                 "slot_name": <slot_name>,
            },
            "query": <query>,
        }
        ```
    """
    content = []
    input_file = Path(input_file).expanduser()
    with input_file.open() as f:
        reader = csv.reader(f, delimiter='\t')
        for row_i, row in enumerate(reader):
            row_content = {'intent': row[0]}
            slots = []
            if row[1]:
                for slot_str in row[1].split(','):
                    start, end, slot_name = slot_str.split(':')
                    slots.append({'start': int(start), 'end': int(end), 'name': slot_name})
                slots = sorted(slots, key=lambda x: x['start'])
                for i in range(len(slots) - 1):
                    if slots[i]['end'] > slots[i + 1]['start']:
                        raise ValueError(
                            f"Slots {slots[i]} and {slots[i + 1]} from row {row_i} (starting from 0) from file "
                            f"{input_file} overlap."
                        )
            row_content['slots'] = slots
            row_content['query'] = row[2]
            content.append(row_content)
    return content


def tokenize_with_alignment(
    query: str, tokenizer: PreTrainedTokenizerBase
) -> Tuple[List[str], List[int], List[int], List[Tuple[int, int]]]:
    tokenized_query = tokenizer.tokenize(query)
    tokens = combine_subwords(tokenized_query)
    starts, ends, unk_zones = [], [], []
    pos_in_query = 0
    unk_zone_start = None
    for token_i, token in enumerate(tokens):
        if token == tokenizer.unk_token:
            if unk_zone_start is None:
                unk_zone_start = pos_in_query
            starts.append(None)
            ends.append(None)
        else:
            while pos_in_query < len(query) and query[pos_in_query: pos_in_query + len(token)] != token:
                pos_in_query += 1
            if pos_in_query >= len(query):
                raise RuntimeError(f"Tokenization of a query lead to removal ")
            if unk_zone_start is not None:
                unk_zones.append((unk_zone_start, pos_in_query))
                unk_zone_start = None
            starts.append(pos_in_query)
            pos_in_query += len(token)
            ends.append(pos_in_query)
    return tokens, starts, ends, unk_zones


def slots_to_bio(
    queries: List[str],
    slots: List[SlotsType],
    tokenizer: Optional[PreTrainedTokenizerBase] = None,
    require_correct_slots: bool = True
) -> List[List[str]]:
    if tokenizer is None:
        tokenizer = BertTokenizer.from_pretrained('bert-base-cased')
    bio: List[List[str]] = []
    for query_idx, (query, query_slots) in enumerate(zip(queries, slots)):
        tokens, starts, ends, unk_zones = tokenize_with_alignment(query, tokenizer)
        query_bio = ['O'] * len(tokens)
        for slot in query_slots:
            if slot['end'] <= slot['start']:
                if require_correct_slots:
                    raise ValueError(
                        f"Slot '{slot['name']}' end offset {slot['end']} cannot be less or equal to slot start offset "
                        f"{slot['start']} in query '{query}' with query index {query_idx}. "
                        f"Slot spans can be computed incorrectly if batch size if too large. Try smaller batch size. "
                        f"The error can occur if test data mark up is wrong."
                    )
                else:
                    continue
            slot_start_token_idx, slot_end_token_idx = None, None
            for i, start in enumerate(starts):
                if start == slot['start']:
                    slot_start_token_idx = i
                    query_bio[slot_start_token_idx] = f'B-{slot["name"]}'
                    break
            if slot_start_token_idx is None:
                if require_correct_slots:
                    raise ValueError(
                        f"Could not find a beginning of slot {slot} in query '{query}'. Acquired tokens: {tokens}. "
                        f"Aligned token beginning offsets: {starts}. Aligned token ending offsets: {ends}. An error "
                        f"occurred during processing of {query_idx}th query. This error can appear if query mark up "
                        f"is broken."
                    )
                else:
                    continue
            for i, end in enumerate(ends):
                if end == slot['end']:
                    for j in range(slot_start_token_idx + 1, i + 1):
                        query_bio[j] = f'I-{slot["name"]}'
        bio.append(query_bio)
    return bio


def pack_slots_to_dict_format(
    slots: List[List[str]], starts: List[List[int]], ends: List[List[int]]
) -> List[SlotsType]:
    output: List[SlotsType] = []
    for query_slots, query_starts, query_ends in zip(slots, starts, ends):
        output.append(
            [
                {'start': start, 'end': end + 1, 'name': slot}
                for start, end, slot in zip(query_starts, query_ends, query_slots)
            ]
        )
    return output


def slots_classification_report(
    y_true: List[List[str]], y_pred: List[List[str]], output_dict: bool
) -> Union[str, Dict[str, Dict[str, Union[int, float]]]]:
    encoder = LabelEncoder()
    all_slots = list({ele for row in y_true for ele in row}.union({ele for row in y_pred for ele in row}))
    encoder.fit(all_slots)
    y_true, y_pred = list(itertools.chain(*y_true)), list(itertools.chain(*y_pred))
    y_truth = encoder.transform(y_true)
    y_pred = encoder.transform(y_pred)
    target_names = encoder.classes_
    return classification_report(y_truth, y_pred, target_names=target_names, output_dict=output_dict)


def intent_slots_classification_report(
    input_file: Path,
    nlp_service: riva_api.NLPService,
    model: str,
    batch_size: int,
    language_code: str,
    output_dict: bool,
) -> Union[
    Tuple[str, str],
    Tuple[Dict[str, Dict[str, Union[int, float]]]], Dict[str, Dict[str, Union[int, float]]]
]:
    test_data = read_tsv_file(input_file)
    queries = [elem['query'] for elem in test_data]
    tokens, slots, _, token_starts, token_ends = riva_api.nlp.classify_tokens_batch(
        nlp_service, queries, model, batch_size, language_code
    )
    intents, _ = riva_api.nlp.classify_text_batch(nlp_service, queries, model, batch_size, language_code)
    intent_report = classification_report([elem['intent'] for elem in test_data], intents, output_dict=output_dict)
    ground_truth_bio = slots_to_bio(queries, [elem['slots'] for elem in test_data])
    predicted_bio = slots_to_bio(
        queries, pack_slots_to_dict_format(slots, token_starts, token_ends), require_correct_slots=False
    )
    per_label_slot_report = slots_classification_report(ground_truth_bio, predicted_bio, output_dict=output_dict)
    return intent_report, per_label_slot_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Program to print classification reports for intent and slot test data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--model", default="riva_intent_weather", type=str, help="Model on TRTIS to execute")
    parser.add_argument(
        "--input-file",
        type=Path,
        required=True,
        help="A path to an input .tsv file. An input file has to be in a format <intent>TAB<slots>TAB<query>. "
        "<slots> field contains several comma separated slots, e.g.: <slot>,<slot>. If there are no slots, then "
        "<slots> is an empty string. Each slot has a format <start>:<end>:<slot_class> where <start> and <end> "
        "are start and end of a slice applied to a query to get a slot, e.g. in an a sample "
        "'<intent><TAB>0:4:animal<TAB>cats are nice' `start=0`, `end=4`, `query='cats are nice'` "
        "and slot `animal='cats'` is acquired by `query[start:end]`."
        "`data/nlp_test_metrics/weather.fixed.eval.tsv` is an example of a correct input file.",
    )
    parser.add_argument("--language-code", default='en-US', help="A language of a model.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="How many examples are sent to server in one request. Currently only `1` is supported.",
    )
    parser = add_connection_argparse_parameters(parser)
    args = parser.parse_args()
    if args.batch_size > 1:
        warnings.warn()
    args.input_file = args.input_file.expanduser()
    return args


def main() -> None:
    args = parse_args()
    auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.server)
    service = riva_api.NLPService(auth)
    intent_report, slot_report = intent_slots_classification_report(
        args.input_file, service, args.model, args.batch_size, args.language_code, False
    )
    print(intent_report)
    print(slot_report)


if __name__ == "__main__":
    main()
