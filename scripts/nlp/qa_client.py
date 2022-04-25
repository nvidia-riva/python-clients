# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import argparse
import os

import grpc
import riva_api.proto.riva_nlp_pb2 as rnlp
import riva_api.proto.riva_nlp_pb2_grpc as rnlp_srv


def get_args():
    parser = argparse.ArgumentParser(description="Riva Question Answering client sample")
    parser.add_argument("--server", type=str, help="URI to access Riva server")
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
    parser.add_argument("--ssl_cert", type=str, default="", help="Path to SSL client certificatates file")
    parser.add_argument(
        "--use_ssl", default=False, action='store_true', help="Boolean to control if SSL/TLS encryption should be used"
    )
    return parser.parse_args()


parser = get_args()

riva_uri = parser.server
if riva_uri is None:
    if "RIVA_URI" in os.environ:
        riva_uri = os.getenv("RIVA_URI")
    else:
        riva_uri = "localhost:50051"
grpc_server = riva_uri
if parser.ssl_cert != "" or parser.use_ssl:
    root_certificates = None
    if parser.ssl_cert != "" and os.path.exists(parser.ssl_cert):
        with open(parser.ssl_cert, 'rb') as f:
            root_certificates = f.read()
    creds = grpc.ssl_channel_credentials(root_certificates)
    channel = grpc.secure_channel(riva_uri, creds)
else:
    channel = grpc.insecure_channel(riva_uri)
riva_nlp = rnlp_srv.RivaLanguageUnderstandingStub(channel)
req = rnlp.NaturalQueryRequest()
req.query = parser.query
req.context = parser.context
resp = riva_nlp.NaturalQuery(req)
print(resp)
