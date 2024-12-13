# Copyright (c) 2020, NVIDIA CORPORATION. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#  * Neither the name of NVIDIA CORPORATION nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#!/usr/bin/env python

import argparse
import os
import sys

import grpc
import riva.client.proto.riva_nmt_pb2 as riva_nmt
import riva.client.proto.riva_nmt_pb2_grpc as riva_nmt_srv

import riva.client
from riva.client.argparse_utils import add_connection_argparse_parameters


def read_dnt_phrases_file(file_path):
    dnt_phrases_dict = {}
    if file_path:
        try:
            with open(file_path, "r") as infile:
                for line in infile:
                    # Trim leading and trailing whitespaces
                    line = line.strip()

                    if line:
                        pos = line.find("##")
                        if pos != -1:
                            # Line contains "##"
                            key = line[:pos].strip()
                            value = line[pos + 2 :].strip()
                        else:
                            # Line doesn't contain "##"
                            key = line.strip()
                            value = ""

                        # Add the key-value pair to the dictionary
                        if key:
                            dnt_phrases_dict[key] = value

        except IOError:
            raise RuntimeError(f"Could not open file {file_path}")

    return dnt_phrases_dict

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Neural machine translation by Riva AI Services",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument(
        "--text", default="mir Das ist mir Wurs, bien ich ein berliner", type=str, help="Text to translate"
    )
    inputs.add_argument("--text-file", type=str, help="Path to file for translation")
    parser.add_argument("--dnt-phrases-file", type=str, help="Path to file which contains dnt phrases and custom translations")
    parser.add_argument("--model-name", default="", type=str, help="model to use to translate")
    parser.add_argument(
        "--source-language-code", type=str, default="en-US", help="Source language code (according to BCP-47 standard)"
    )
    parser.add_argument(
        "--target-language-code", type=str, default="en-US", help="Target language code (according to BCP-47 standard)"
    )
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size to use for file translation")
    parser.add_argument("--list-models", default=False, action='store_true', help="List available models on server")
    parser = add_connection_argparse_parameters(parser)

    return parser.parse_args()


def main() -> None:
    def request(inputs,args):
        try:
            dnt_phrases_input = {}
            if args.dnt_phrases_file != None:
                dnt_phrases_input = read_dnt_phrases_file(args.dnt_phrases_file)
            response = nmt_client.translate(
                texts=inputs,
                model=args.model_name,
                source_language=args.source_language_code,
                target_language=args.target_language_code,
                future=False,
                dnt_phrases_dict=dnt_phrases_input,
            )
            for translation in response.translations:
                print(translation.text)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                result = {'msg': 'invalid arg error'}
            elif e.code() == grpc.StatusCode.ALREADY_EXISTS:
                result = {'msg': 'already exists error'}
            elif e.code() == grpc.StatusCode.UNAVAILABLE:
                result = {'msg': 'server unavailable check network'}
            else:
                result = {'msg': 'error code:{}'.format(e.code())}
            print(f"{result['msg']} : {e.details()}")

    args = parse_args()

    auth = riva.client.Auth(args.ssl_cert, args.use_ssl, args.server, args.metadata)
    nmt_client = riva.client.NeuralMachineTranslationClient(auth)

    if args.list_models:

        response = nmt_client.get_config(args.model_name)
        print(response)
        return

    if args.text_file != None and os.path.exists(args.text_file):
        with open(args.text_file, "r") as f:
            batch = []
            for line in f:
                line = line.strip()
                if line != "":
                    batch.append(line)
                if len(batch) == args.batch_size:
                    request(batch, args)
                    batch = []
            if len(batch) > 0:
                request(batch, args)
        return

    if args.text != "":
        request([args.text], args)


if __name__ == '__main__':
    main()
