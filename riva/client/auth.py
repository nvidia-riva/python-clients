# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import os
from pathlib import Path
from typing import List, Optional, Tuple, Union

import grpc


def create_channel(
    ssl_cert: Optional[Union[str, os.PathLike]] = None,
    use_ssl: bool = False,
    uri: str = "localhost:50051",
    async_: bool = False,
) -> grpc.Channel:
    lib = grpc.aio if async_ else grpc
    if ssl_cert is not None or use_ssl:
        root_certificates = None
        if ssl_cert is not None:
            ssl_cert = Path(ssl_cert).expanduser()
            with open(ssl_cert, 'rb') as f:
                root_certificates = f.read()
        creds = grpc.ssl_channel_credentials(root_certificates)
        channel = lib.secure_channel(uri, creds)
    else:
        channel = lib.insecure_channel(uri)
    return channel


class Auth:
    def __init__(
        self,
        ssl_cert: Optional[Union[str, os.PathLike]] = None,
        use_ssl: bool = False,
        uri: str = "localhost:50051",
        async_: bool = False,
    ) -> None:
        """
        A class responsible for establishing connection with a server and providing security metadata. Please take into
        account, that depending on :param:`async_` value an :class:`Auth` instance can be used in async of synchronous
        services.

        Args:
            ssl_cert (:obj:`Union[str, os.PathLike]`, `optional`): a path to SSL certificate file. If :param:`use_ssl`
                is :obj:`False` and :param:`ssl_cert` is not :obj:`None`, then SSL is used.
            use_ssl (:obj:`bool`, defaults to :obj:`False`): whether to use SSL. If :param:`ssl_cert` is :obj:`None`,
                then SSL is still used but with default credentials.
            uri (:obj:`str`, defaults to :obj:`"localhost:50051"`): a Riva URI.
            async_ (:obj:`bool`, defaults to :obj:`False`): whether an :class:`Auth` instance uses for connection
                ``aio`` :class:`grpc.aio.Channel` instead of :class:`grpc.Channel`. If :param:`async_` is ``True``,
                then only async services like :class:`riva.client.ASRServiceAio` can be used. If :param:`async_` is
                ``False``, then only synchronous services like :class:`riva.client.ASRService` can be used.
        """
        self.ssl_cert: Optional[Path] = None if ssl_cert is None else Path(ssl_cert).expanduser()
        self.uri: str = uri
        self.use_ssl: bool = use_ssl
        self.async_ = async_
        self.channel: grpc.Channel = create_channel(self.ssl_cert, self.use_ssl, self.uri, async_)

    def get_auth_metadata(self) -> List[Tuple[str, str]]:
        """
        Will become useful when API key and OAUTH tokens will be enabled.

        Metadata for authorizing requests. Should be passed to stub methods.

        Returns:
            :obj:`List[Tuple[str, str]]`: an empty list.
        """
        metadata = []
        return metadata

    def channel_async_check(self, class_: type, async_expected: bool) -> None:
        full_class_name = class_.__module__ + '.' + class_.__name__
        if async_expected and not self.async_:
            raise ValueError(
                f"Class {full_class_name} expects an `Auth` instance with asynchronous channel. To fix this error, "
                f"pass an `Auth` instantiated with `async_=True` to {full_class_name} constructor."
            )
        if not async_expected and self.async_:
            raise ValueError(
                f"Class {full_class_name} expects an `Auth` instance with synchronous channel. To fix this error, "
                f"pass an `Auth` instantiated with `async_=False` to {full_class_name} constructor."
            )
