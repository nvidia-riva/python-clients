# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import time

import riva.client
from riva.client.argparse_utils import add_connection_argparse_parameters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Client app to restore Punctuation and Capitalization with Riva",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--model",
        help="Model on Riva Server to execute. If this parameter is missing, then the server will try to select a "
        "first available Punctuation & Capitalization model.",
    )
    parser.add_argument("--query", default="can you prove that you are self aware", help="Input Query")
    parser.add_argument(
        "--run-tests",
        action='store_true',
        help="Flag to run sanity tests. If this option is chosen, then options `--query` and `--interactive` are "
        "ignored and a model is run on several hardcoded examples and numbers of passed and failed tests are shown.",
    )
    parser.add_argument(
        "--interactive",
        action='store_true',
        help="If this option is set, then `--query` argument is ignored and the script suggests user to enter "
        "queries to standard input.",
    )
    parser.add_argument(
        "--language-code", default="en-US", help="Language code of the model to be used.",
    )
    parser = add_connection_argparse_parameters(parser)
    return parser.parse_args()


def run_punct_capit(args: argparse.Namespace) -> None:
    auth = riva.client.Auth(args.ssl_cert, args.use_ssl, args.server)
    nlp_service = riva.client.NLPService(auth)
    if args.interactive:
        while True:
            query = input("Enter a query: ")
            start = time.time()
            result = riva.client.nlp.extract_most_probable_transformed_text(
                nlp_service.punctuate_text(
                    input_strings=query, model_name=args.model, language_code=args.language_code
                )
            )
            end = time.time()
            print(f"Inference complete in {(end - start) * 1000:.4f} ms")
            print(result, end='\n' * 2)
    else:
        print(
            riva.client.nlp.extract_most_probable_transformed_text(
                nlp_service.punctuate_text(
                    input_strings=args.query, model_name=args.model, language_code=args.language_code
                )
            )
        )


def run_tests(args: argparse.Namespace) -> int:
    test_inputs = {
        "en-US": [
            "can you prove that you are self aware",
            "will you have $103 and ₩111 at 12:45 pm",
            # "Hi My name is markus stoinis How are you ?", # This fails for onnx model
            "the train leaves station by 09:45 A.M. and reaches destination in 3 hours",
            "Loona (stylized as LOOΠΔ, Korean: 이달의 소녀; Hanja: Idarui Sonyeo; lit. ''Girl of the Month'') is "
            "a South Korean girl group formed by Blockberry Creative",
            "i just want to start with a little bit of a word of warning and that is my job here tonight is to "
            "be a little bit of a doctor bring me down so bear with me for a few minutes and know that after "
            "this things will get lighter and brighter so let's start i know that many of you have heard the "
            "traveler's adage take nothing but pictures leave nothing but footprints well i'm going to say "
            "i don't think that's either as benign nor as simple as it sounds particularly for those of us in "
            "industries who are portraying people in poor countries in developing countries and portraying the "
            "poor and those of us in those industries are reporters researchers and people working for ngos i "
            "suspect there are a lot of us in those industries in the audience",
            "if water is held at 100 °C [212 °F] for one minute most micro-organisms and viruses are inactivated",
        ],
        "es-US": ["bien y qué regalo vas a abrir primero", "ya hemos hablado de eso no"],
        "de-DE": ["aber weißt du wer den stein wirklich ins rollen gebracht hat", "anna weißt du wo charlotte ist"],
        "fr-FR": [
            "à l'adresse suivante quarante quatre rue de saint genès",
            "qui a écrit le script de infirmière en chef",
            "en ce moment avec la guerre en ukraine il faut être très prudent dans les investissements en bourse",
        ],
        "hi-IN": ["नया क्या है", "मेरे परिवार को Tom पसंद था", "इलाहाबाद मार्केट में लगी आग महिला की मौत"],
        "zh-CN": [
            "关于经济纠纷的说法村民们偏向于两种说法",
            "这样得来的学习成绩除了字面意义上的阿拉伯数字之外大约也没有多少积极意义",
            "this is a text关于经济纠纷的说法村民们偏向于两种说法another text",
            "人工智能（AI）正在蓬勃发展",
        ],
    }
    test_output_ref = {
        "en-US": [
            "Can you prove that you are self aware?",
            "Will you have $103 and ₩111 at 12:45 pm?",
            # "Hi, My name is Markus Stoinis. How are you ?",
            "The train leaves station by 09:45 A.M. and reaches destination in 3 hours.",
            "Loona (stylized as LOOΠΔ, Korean: 이달의 소녀; Hanja: Idarui Sonyeo; lit. ''Girl of the Month'') is "
            "a South Korean girl group formed by Blockberry Creative.",
            "I just want to start with a little bit of a word of warning, and that is my job here tonight is "
            "to be a little bit of a doctor. Bring me down, so bear with me for a few minutes and know that "
            "after this things will get lighter and brighter. So let's start. I know that many of you have "
            "heard the traveler's adage Take nothing but pictures, leave nothing but footprints. Well, I'm "
            "going to say, I don't think that's either as benign nor as simple as it sounds, particularly for "
            "those of us in industries who are portraying people in poor countries in developing countries and "
            "portraying the poor and those of us in those industries are reporters, researchers and people "
            "working for ngos. I suspect there are a lot of us in those industries in the audience.",
            "If water is held at 100 °C [212 °F] for one minute, most micro-organisms and viruses are inactivated.",
        ],
        "es-US": ["Bien. ¿y qué regalo vas a abrir primero?", "ya hemos hablado de eso, no?"],
        "de-DE": [
            "aber. Weißt du, wer den Stein wirklich ins Rollen gebracht hat,",
            "Anna, weißt du wo Charlotte ist?",
        ],
        "fr-FR": [
            "à l'adresse suivante quarante quatre rue de Saint-Genès",
            "Qui a écrit le script de infirmière en chef?",
            "En ce moment avec la guerre en Ukraine, il faut être très prudent dans les investissements en bourse.",
        ],
        "hi-IN": ["नया क्या है?", "मेरे परिवार को Tom पसंद था।", "इलाहाबाद मार्केट में लगी आग, महिला की मौत"],
        "zh-CN": [
            "关于经济纠纷的说法，村民们偏向于两种说法。",
            "这样得来的学习成绩，除了字面意义上的阿拉伯数字之外，大约也没有多少积极意义。",
            "this is a text。关于经济纠纷的说法，村民们偏向于两种说法。another text",
            "人工智能（AI）正在蓬勃发展。",
        ],
    }

    auth = riva.client.Auth(args.ssl_cert, args.use_ssl, args.server)
    nlp_service = riva.client.NLPService(auth)

    fail_count = 0
    for input_, output_ref in zip(test_inputs[args.language_code], test_output_ref[args.language_code]):
        pred = riva.client.nlp.extract_most_probable_transformed_text(
            nlp_service.punctuate_text(
                input_strings=input_,
                model_name=args.model,
                language_code=args.language_code,
            )
        )
        print(f"Input: {input_}")
        print(f"Output: {pred}")
        if pred != output_ref:
            print(f"Output mismatched!")
            print(f"Output reference: {output_ref}")
            fail_count += 1

    print(f"Tests passed: {len(test_inputs) - fail_count}")
    print(f"Tests failed: {fail_count}")
    return fail_count


def main() -> None:
    args = parse_args()
    if args.run_tests:
        exit(run_tests(args))
    else:
        run_punct_capit(args)


if __name__ == '__main__':
    main()
