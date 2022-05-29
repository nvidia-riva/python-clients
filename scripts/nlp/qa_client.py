# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import argparse

import riva_api
from riva_api.argparse_utils import add_connection_argparse_parameters


def parse_args():
    parser = argparse.ArgumentParser(
        description="Riva Question Answering client sample", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--query", type=str, default="How much carbon dioxide was released in 2005?", help="Query for the QA API"
    )
    parser.add_argument(
        "--context",
        type=str,
        default="In 2010 the Amazon rainforest experienced another severe drought, in some ways more extreme than the "
        "2005 drought. The affected region was approximate 1,160,000 square miles (3,000,000 km2) of "
        "rainforest, compared to 734,000 square miles (1,900,000 km2) in 2005. The 2010 drought had three "
        "epicenters where vegetation died off, whereas in 2005 the drought was focused on the southwestern "
        "part. The findings were published in the journal Science. In a typical year the Amazon absorbs 1.5 "
        "gigatons of carbon dioxide; during 2005 instead 5 gigatons were released and in 2010 8 gigatons were "
        "released.",
        help="Context for the QA API",
    )
    parser = add_connection_argparse_parameters(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.server)
    service = riva_api.NLPService(auth)
    resp = service.natural_query(args.query, args.context)
    print(resp)


if __name__ == "__main__":
    main()

