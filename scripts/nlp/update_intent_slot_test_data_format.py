# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Transforms old style file for intent classification and entities classification "
        "to new style format. Old style is '<intent>TAB<entities>TAB<query>' where <query> is in format "
        "'BOS <intent> <text> EOS'. This script keeps only <text> in <query> and removes auxiliary "
        "<intent> field and BOS and EOS."
    )
    parser.add_argument("--input-file", type=Path, help="A path to an input .tsv file.", required=True)
    parser.add_argument("--output-file", type=Path, help="A path to an output .tsv file.", required=True)
    args = parser.parse_args()
    args.input_file = args.input_file.expanduser()
    args.output_file = args.output_file.expanduser()
    return args


def main() -> None:
    args = parse_args()
    with args.input_file.open() as in_f, args.output_file.open('w') as out_f:
        for line_i, line in enumerate(in_f):
            intent, slots, query = line.split('\t')
            words = query.split()
            new_query = ' '.join(words[2:-1])
            if slots:
                slots = slots.split(',')
                new_slots = []
                offset = len(words[0]) + len(words[1]) + 2
                for slot in slots:
                    try:
                        start, end, name = slot.split(':')
                    except ValueError:
                        print(slot)
                        print(line_i)
                        raise
                    start, end = int(start), int(end)
                    if start < offset or end < offset:
                        raise ValueError(
                            f"Slot borders start={start}, end={end} in line {line_i} in file {args.input_file}"
                        )
                    slot = ':'.join([str(start - offset), str(end - offset), name])
                    new_slots.append(slot)
                new_slots = ','.join(new_slots)
            else:
                new_slots = ''
            out_f.write('\t'.join([intent, new_slots, new_query]) + '\n')


if __name__ == "__main__":
    main()
