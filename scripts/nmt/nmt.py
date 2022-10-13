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
import riva_api.riva_nmt_pb2 as riva_nmt
import riva_api.riva_nmt_pb2_grpc as riva_nmt_srv


def get_args():
    parser = argparse.ArgumentParser(description="Streaming transcription via Riva AI Services")
    parser.add_argument("--riva_uri", default="localhost:50051", type=str, help="URI to GRPC server endpoint")
    parser.add_argument(
        "--text", default="mir Das ist mir Wurs, bien ich ein berliner", type=str, help="Text to translate"
    )
    parser.add_argument("--model_name", default="riva-nmt", type=str, help="model to use to translate")
    parser.add_argument(
        "--src_language", default="en", type=str, help="Source language (according to BCP-47 standard)"
    )
    parser.add_argument(
        "--tgt_language", default="de", type=str, help="Target language (according to BCP-47 standard)"
    )
    parser.add_argument("--ssl_cert", type=str, default="", help="Path to SSL client certificatates file")
    parser.add_argument("--text_file", type=str, help="Path to file for translation")
    parser.add_argument("--batch_size", type=int, default=8, help="Batch size to use for file translation")
    parser.add_argument("--list_models", default=False, action='store_true', help="List available models")
    parser.add_argument(
        "--use_ssl", default=False, action='store_true', help="Boolean to control if SSL/TLS encryption should be used"
    )

    return parser.parse_args()


def main():
    def request(inputs):
        nmt_client = riva_nmt_srv.RivaTranslationStub(channel)
        nmt_request = riva_nmt.TranslateTextRequest()
        nmt_request.texts.extend(inputs)
        nmt_request.model = args.model_name
        nmt_request.source_language = args.src_language
        nmt_request.target_language = args.tgt_language
        try:
            response = nmt_client.TranslateText(nmt_request)
            for translation in response.translations:
                print(translation.text)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                result = {'msg': 'invalid arg error'}
            elif e.code() == grpc.StatusCode.ALREADY_EXISTS:
                result = {'msg': 'already exists error'}
            elif e.code() == grpc.StatusCode.UNAVAILABLE:
                result = {'msg': 'server unavailable check network'}
            print(f"{result['msg']} : {e.details()}")

    args = get_args()

    if args.ssl_cert != "" or args.use_ssl:
        root_certificates = None
        if args.ssl_cert != "" and os.path.exists(args.ssl_cert):
            with open(args.ssl_cert, 'rb') as f:
                root_certificates = f.read()
        creds = grpc.ssl_channel_credentials(root_certificates)
        channel = grpc.secure_channel(args.riva_uri, creds)
    else:
        riva_uri = os.getenv("RIVA_URI")
        if riva_uri:
            print(f"Using ENV variable:{riva_uri}")
            channel = grpc.insecure_channel(riva_uri)
        else:
            channel = grpc.insecure_channel(args.riva_uri)

    if args.list_models == True:
        nmt_client = riva_nmt_srv.RivaTranslationStub(channel)
        response = nmt_client.ListSupportedLanguagePairs(riva_nmt.AvailableLanguageRequest())
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
                    request(batch)
                    batch = []
            if len(batch) > 0:
                request(batch)
        return

    if args.text != "":
        request([args.text])


if __name__ == '__main__':
    main()
