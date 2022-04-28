#!/usr/bin/env python
import argparse
import time

from riva_nlp import BertPunctuator


def print_result(result, duration=0):
    print("Inference complete in {:.4f} ms".format(duration * 1000))
    print(result)
    print("\n")


def get_args():
    parser = argparse.ArgumentParser(description="Example punctuator client")
    parser.add_argument("--server", default="localhost:8001", type=str, help="URI to GRPC server endpoint")
    parser.add_argument("--model", default="punctuator", type=str, help="Model on TRTIS to execute")
    parser.add_argument(
        "--query", type=str, default=None, help="Run in CLI additional_info with supplied query, run interactive if not supplied"
    )
    parser.add_argument("--ssl_cert", type=str, default="", help="Path to SSL client certificatates file")
    parser.add_argument(
        "--use_ssl", default=False, action='store_true', help="Boolean to control if SSL/TLS encryption should be used"
    )
    return parser.parse_args()


def interactive_punct():
    args = get_args()
    client = BertPunctuator(args.server, model_name=args.model, use_ssl=args.use_ssl, ssl_cert=args.ssl_cert)

    if args.query:
        result = client.run(args.query)
        print_result(result[0])
    else:
        # do a warmup / test batch size > 1
        # results = client.run([
        #    "I'd like to drive from San Francisco to New Mexico for cheap",
        #    "I want to fly to California",
        #    "How much would it cost to fly from Atlanta to New York tomorrow?"]
        # )
        # result is a list of strings ['tokens', 'with', 'punctuation'])
        while True:
            query = input("Enter a query: ")
            start = time.time()
            result = client.run(query)[0]
            end = time.time()
            print_result(result, duration=end - start)
