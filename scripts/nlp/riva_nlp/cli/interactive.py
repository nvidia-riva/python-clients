#!/usr/bin/env python
import argparse
import time

from riva_nlp import BertIntentSlotClient


def print_result(result, duration=0):
    print("Inference complete in {:.4f} ms".format(duration * 1000))
    print("Intent:", result[0])
    print("Intent Score:", result[1])
    print("Slots:", result[2])
    print("Slots Scores:", result[4])
    if len(result[3]) > 0:
        print("Combined: ", end="")
        for token, slot in zip(result[3], result[2]):
            print("{}{}".format(token, "(" + slot + ")" if slot != 'O' else ""), end=" ")
        print("\n")


def get_args():
    parser = argparse.ArgumentParser(description="Example intent/slot client")
    parser.add_argument("--server", default="localhost:50051", type=str, help="URI to GRPC server endpoint")
    parser.add_argument("--model", default="atis_intent_slot", type=str, help="Model on TRTIS to execute")
    parser.add_argument(
        "--query", type=str, default=None, help="Run in CLI additional_info with supplied query, run interactive if not supplied"
    )
    parser.add_argument("--ssl_cert", type=str, default="", help="Path to SSL client certificatates file")
    parser.add_argument(
        "--use_ssl", default=False, action='store_true', help="Boolean to control if SSL/TLS encryption should be used"
    )
    return parser.parse_args()


def interactive_main():
    args = get_args()
    client = BertIntentSlotClient(args.server, model_name=args.model, use_ssl=args.use_ssl, ssl_cert=args.ssl_cert)

    if args.query:
        start = time.time()
        result = client.run(args.query)[0]
        end = time.time()
        print_result(result, duration=end - start)
    else:
        # do a warmup / test batch size > 1
        # results = client.run([
        #    "I'd like to drive from San Francisco to New Mexico for cheap",
        #    "I want to fly to California",
        #    "How much would it cost to fly from Atlanta to New York tomorrow?"]
        # )
        # results are list of 2-tuples: ('intent', ['slot class_1', ..., 'slot class_n'])
        while True:
            query = input("Enter a query: ")
            start = time.time()
            result = client.run(query)[0]
            end = time.time()
            print_result(result, duration=end - start)


if __name__ == "__main__":
    interactive_main()
