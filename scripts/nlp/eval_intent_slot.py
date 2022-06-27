# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

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

import riva.client
from riva.client.argparse_utils import add_connection_argparse_parameters


def combine_subwords(tokens: List[str]) -> List[str]:
    """
    This function combines subwords into single word

    Args:
        tokens (:obj:`List[str]`): a list tokens generated using BERT tokenizer which may have subwords
            separated by "##".

    Returns:
        :obj:`List[str]`: a list of tokens which do not contain "##". Instead such tokens are concatenated with
        preceding tokens.
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
    <intent_name>TAB<slots>TAB<query>
    <slots> := <slot>,<slot>
    <slot> := <slice_start>:<slice_end>:<slot_name>
    ```
    Args:
        input_file (:obj:`Union[str, os.PathLike]`): a path to an input file

    Returns:
        :obj:`List[Dict[str, Union[str, List[Dict[str, Union[int, str]]]]]]`: a list of examples for testing. Each
        example has format:
        ```
        {
            "intent": <intent_name>,
            "slots": {
                 "start": <slice_start>,
                 "end": <slice_end>,
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
) -> Tuple[List[str], List[Optional[int]], List[Optional[int]], List[Tuple[int, int]]]:
    """
    Tokenizes a query :param:`query` using tokenizer :param:`tokenizer`, combines subwords, and calculates slices of
    tokens in the query.

    Args:
        query (:obj:`str`): an input query.
        tokenizer (:obj:`PreTrainedTokenizerBase`): a HuggingFace tokenizer used for tokenizing :param:`query`.

    Returns:
        :obj:`tuple`: a tuple containing 3 lists of identical length and 4th list which length can differ
        from the first 3:

            - tokens (:obj:`List[str]`): a list of tokens acquired from :param:`query`.
            - starts (:obj:`List[Optional[int]]`): a list of slice starts (slices used for extracting tokens from
                :param:`query`). If a token is UNK, then a corresponding :obj:`starts` element is :obj:`None`.
            - ends (:obj:`List[Optional[int]]`): a list of slice ends (slices used for extracting tokens from
                :param:`query`). If a token is UNK, then a corresponding :obj:`ends` element is :obj:`None`.
            - unk_zones (:obj:`List[Tuple[int, int]]`): a tuple with slices which show position of UNK tokens and
                spaces surrounding UNK tokens.

    Raises:
        :obj:`RuntimeError`: if a token is not found in a query.
    """
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
                raise RuntimeError(
                    f"Tokenization of a query '{query}' lead to removal of token '{token}'. Tokens: {tokens}."
                )
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
    """
    Creates BIO markup for queries in :param:`queries` according slots described in :param:`slots`.

    Args:
        queries (:obj:`List[str]`): a list of input queries
        slots (:obj:`List[List[Dict[str, Union[int, str]]]]`): a list of slots for all queries. Slots for a query is a
            list of dictionaries with keys :obj:`"start"`, :obj:`"end"`, :obj:`"name"`. :obj:`"start"` and :obj:`"end"`
            if used as slice start and end for corresponding give a slot text.
        tokenizer (:obj:`PreTrainedTokenizerBase`, `optional`): a tokenizer used for queries tokenization.
            If :obj:`None`, then `"bert-base-cased"` is used.
        require_correct_slots (:obj:`bool`, defaults to :obj:`True`): if :obj:`True`, then matching of tokens and
            slot spans is checked and an error is raised if there is no match. Set this to :obj:`True` if you prepare
            ground truth and to :obj:`False` if you prepare predictions.

    Returns:
        :obj:`List[List[str]]`: a BIO markup for queries.
    """
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
                        f"The error can occur if test data mark up is wrong."
                    )
                else:
                    continue
            slot_start_token_idx, slot_end_token_idx = None, None
            for token_i, start in enumerate(starts):
                if start == slot['start']:
                    slot_start_token_idx = token_i
                    query_bio[slot_start_token_idx] = f'B-{slot["name"]}'
                    break
            if slot_start_token_idx is None:
                if require_correct_slots:
                    raise ValueError(
                        f"Could not find a beginning of slot {slot} in a query '{query}'. Acquired tokens: {tokens}. "
                        f"Aligned token beginning offsets: {starts}. Aligned token ending offsets: "
                        f"{ends}. An error occurred during processing of {query_idx}th query. This error "
                        f"can appear if query mark up is broken."
                    )
                else:
                    continue
            found_end = False
            for token_i, end in enumerate(ends):
                if end == slot['end']:
                    found_end = True
                    for j in range(slot_start_token_idx + 1, token_i + 1):
                        query_bio[j] = f'I-{slot["name"]}'
            if not found_end and require_correct_slots:
                raise ValueError(
                    f"Could not find an end of slot {slot} in a query '{query}'. Acquired tokens: {tokens}. "
                    f"Aligned token beginning offsets: {starts}. Aligned token ending offsets: "
                    f"{ends}. An error occurred during processing of {query_idx}th query. This error "
                    f"can appear if query mark up is broken."
                )
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
    nlp_service: riva.client.NLPService,
    model: str,
    batch_size: int,
    language_code: str,
    output_dict: bool,
    max_async_requests_to_queue: int,
) -> Union[
    Tuple[str, str],
    Tuple[Dict[str, Dict[str, Union[int, float]]]], Dict[str, Dict[str, Union[int, float]]]
]:
    test_data = read_tsv_file(input_file)
    queries = [elem['query'] for elem in test_data]
    tokens, slots, _, token_starts, token_ends = riva.client.nlp.classify_tokens_batch(
        nlp_service, queries, model, batch_size, language_code, max_async_requests_to_queue
    )
    intents, _ = riva.client.nlp.classify_text_batch(
        nlp_service, queries, model, batch_size, language_code, max_async_requests_to_queue
    )
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
    parser.add_argument(
        "--max-async-requests-to-queue",
        type=int,
        default=500,
        help="If greater than 0, then data is processed in async manner. Up to`--max-async-requests-to-queue` "
        "requests are asynchronous requests are sent and then the program will wait for results. When results are "
        "returned, new `--max-async-requests-to-queue` are sent.",
    )
    parser = add_connection_argparse_parameters(parser)
    args = parser.parse_args()
    if args.max_async_requests_to_queue < 0:
        parser.error(
            f"Parameter `--max-async-requests-to-queue` has not negative, whereas {args.max_async_requests_to_queue} "
            f"was given."
        )
    if args.batch_size > 1:
        warnings.warn("Batch size > 1 is not supported because spans may be calculated incorrectly.")
    args.input_file = args.input_file.expanduser()
    return args


def main() -> None:
    args = parse_args()
    auth = riva.client.Auth(args.ssl_cert, args.use_ssl, args.server)
    service = riva.client.NLPService(auth)
    intent_report, slot_report = intent_slots_classification_report(
        args.input_file,
        service,
        args.model,
        args.batch_size,
        args.language_code,
        output_dict=False,
        max_async_requests_to_queue=args.max_async_requests_to_queue
    )
    print(intent_report)
    print(slot_report)


if __name__ == "__main__":
    main()
