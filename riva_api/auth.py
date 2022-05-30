import os
from pathlib import Path
from typing import List, Optional, Tuple, Union

import grpc


def create_channel(
    ssl_cert: Optional[Union[str, os.PathLike]] = None, use_ssl: bool = False, uri: str = "localhost:50051",
) -> grpc.Channel:
    if ssl_cert is not None or use_ssl:
        root_certificates = None
        if ssl_cert is not None:
            ssl_cert = Path(ssl_cert).expanduser()
            with open(ssl_cert, 'rb') as f:
                root_certificates = f.read()
        creds = grpc.ssl_channel_credentials(root_certificates)
        channel = grpc.secure_channel(uri, creds)
    else:
        channel = grpc.insecure_channel(uri)
    return channel


class Auth:
    def __init__(
        self,
        ssl_cert: Optional[Union[str, os.PathLike]] = None,
        use_ssl: bool = False,
        uri: str = "localhost:50051",
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> None:
        self.ssl_cert: Optional[Path] = None if ssl_cert is None else Path(ssl_cert).expanduser()
        self.uri: str = uri
        self.use_ssl: bool = use_ssl
        self.api_key: Optional[str] = api_key
        self.auth_token: Optional[str] = auth_token
        self.channel: grpc.Channel = create_channel(self.ssl_cert, self.use_ssl, self.uri)

    def get_auth_metadata(self) -> List[Tuple[str, str]]:
        metadata = []
        if self.api_key is not None:
            metadata.append(('x-api-key', self.api_key))
        if self.auth_token is not None:
            metadata.append(('authorization', 'Bearer ' + self.auth_token))
        return metadata
