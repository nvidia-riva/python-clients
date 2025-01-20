// SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: MIT

import { Command } from 'commander';

export function addAsrConfigArgparseParameters(program: Command): void {
    program
        .option('--max-alternatives <number>', 'Maximum number of alternative transcripts to return.', '1')
        .option('--profanity-filter', 'Enable profanity filtering.')
        .option('--word-time-offsets', 'Enable word time offset information.')
        .option('--automatic-punctuation', 'Enable automatic punctuation.')
        .option('--no-verbatim-transcripts', 'Disable verbatim transcripts.')
        .option('--metadata <key=value...>', 'Metadata to send to server.')
        .option('--language-code <code>', 'Language code for the request.', 'en-US');
}
