# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import os
from pathlib import Path
from typing import List, Optional, Tuple, Union
import grpc


def create_channel(
    ssl_root_cert: Optional[Union[str, os.PathLike]] = None,
    ssl_client_cert: Optional[Union[str, os.PathLike]] = None,
    ssl_client_key: Optional[Union[str, os.PathLike]] = None,
    use_ssl: bool = False,
    uri: str = "localhost:50051",
    metadata: Optional[List[Tuple[str, str]]] = None,
    options: Optional[List[Tuple[str, str]]] = [],
) -> grpc.Channel:
    def metadata_callback(context, callback):
        callback(metadata, None)

    if ssl_root_cert is not None or ssl_client_cert is not None or ssl_client_key is not None or use_ssl:
        root_certificates = None
        client_certificates = None
        client_key = None
        if ssl_root_cert is not None:
            ssl_root_cert = Path(ssl_root_cert).expanduser()
            with open(ssl_root_cert, 'rb') as f:
                root_certificates = f.read()
        if ssl_client_cert is not None:
            ssl_client_cert = Path(ssl_client_cert).expanduser()
            with open(ssl_client_cert, 'rb') as f:
                client_certificates = f.read()
        if ssl_client_key is not None:
            ssl_client_key = Path(ssl_client_key).expanduser()
            with open(ssl_client_key, 'rb') as f:
                client_key = f.read()
        creds = grpc.ssl_channel_credentials(root_certificates=root_certificates, private_key=client_key, certificate_chain=client_certificates)
        if metadata:
            auth_creds = grpc.metadata_call_credentials(metadata_callback)
            creds = grpc.composite_channel_credentials(creds, auth_creds)
        channel = grpc.secure_channel(uri, creds, options=options)
    else:
        channel = grpc.insecure_channel(uri, options=options)
    return channel


class Auth:
    def __init__(
        self,
        ssl_root_cert: Optional[Union[str, os.PathLike]] = None,
        use_ssl: bool = False,
        uri: str = "localhost:50051",
        metadata_args: List[List[str]] = None,
        ssl_client_cert: Optional[Union[str, os.PathLike]] = None,
        ssl_client_key: Optional[Union[str, os.PathLike]] = None,
        options: Optional[List[Tuple[str, str]]] = [],
    ) -> None:
        """
        Initialize the Auth class for establishing secure connections with a server.

        This class handles SSL/TLS configuration, authentication metadata, and gRPC channel creation
        for secure communication with Riva services.

        Args:
            ssl_root_cert (Optional[Union[str, os.PathLike]], optional): Path to the SSL root certificate file.
                If provided and use_ssl is False, SSL will still be enabled. Defaults to None.
            use_ssl (bool, optional): Whether to use SSL/TLS encryption. If True and ssl_root_cert is None,
                SSL will be used with default credentials. Defaults to False.
            uri (str, optional): The Riva server URI in format "host:port". Defaults to "localhost:50051".
            metadata_args (List[List[str]], optional): List of metadata key-value pairs for authentication.
                Each inner list should contain exactly 2 elements: [key, value]. Defaults to None.
            ssl_client_cert (Optional[Union[str, os.PathLike]], optional): Path to the SSL client certificate file.
                Used for mutual TLS authentication. Defaults to None.
            ssl_client_key (Optional[Union[str, os.PathLike]], optional): Path to the SSL client private key file.
                Used for mutual TLS authentication. Defaults to None.
            options (Optional[List[Tuple[str, str]]], optional): Additional gRPC channel options.
                Each tuple should contain (option_name, option_value). Defaults to [].

        Raises:
            ValueError: If any metadata argument doesn't contain exactly 2 elements (key-value pair).

        Example:
            >>> # Basic connection without SSL
            >>> auth = Auth(uri="localhost:50051")

            >>> # SSL connection with custom certificate
            >>> auth = Auth(
            ...     use_ssl=True,
            ...     ssl_root_cert="/path/to/cert.pem",
            ...     uri="secure-server:50051"
            ... )

            >>> # Connection with authentication metadata
            >>> auth = Auth(
            ...     metadata_args=[["api-key", "your-api-key"], ["user-id", "12345"]],
            ...     uri="auth-server:50051"
            ... )
        """
        self.ssl_root_cert: Optional[Path] = None if ssl_root_cert is None else Path(ssl_root_cert).expanduser()
        self.ssl_client_cert: Optional[Path] = None if ssl_client_cert is None else Path(ssl_client_cert).expanduser()
        self.ssl_client_key: Optional[Path] = None if ssl_client_key is None else Path(ssl_client_key).expanduser()
        self.uri: str = uri
        self.use_ssl: bool = use_ssl
        self.metadata = []
        if metadata_args:
            for meta in metadata_args:
                if len(meta) != 2:
                    raise ValueError(
                        f"Metadata should have 2 parameters in \"key\" \"value\" pair. Receieved {len(meta)} parameters."
                    )
                self.metadata.append(tuple(meta))
        self.channel: grpc.Channel = create_channel(
            self.ssl_root_cert, self.ssl_client_cert, self.ssl_client_key, self.use_ssl, self.uri, self.metadata, options=options
        )

    def get_auth_metadata(self) -> List[Tuple[str, str]]:
        """
        Will become useful when API key and OAUTH tokens will be enabled.

        Metadata for authorizing requests. Should be passed to stub methods.

        Returns:
            :obj:`List[Tuple[str, str]]`: an tuple list of provided metadata
        """
        return self.metadata
