import os
from typing import Optional

import grpc


def create_channel(
    ssl_cert: Optional[os.PathLike] = None, use_ssl: bool = False, riva_uri: str = "localhost:50051",
) -> grpc.Channel:
    if ssl_cert is not None or use_ssl:
        root_certificates = None
        if ssl_cert is not None:
            with open(ssl_cert, 'rb') as f:
                root_certificates = f.read()
        creds = grpc.ssl_channel_credentials(root_certificates)
        channel = grpc.secure_channel(riva_uri, creds)
    else:
        channel = grpc.insecure_channel(riva_uri)
    return channel
