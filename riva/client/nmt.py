# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

from typing import Generator, Optional, Union, List

from grpc._channel import _MultiThreadedRendezvous

import riva.client.proto.riva_nmt_pb2 as riva_nmt
import riva.client.proto.riva_nmt_pb2_grpc as riva_nmt_srv
from riva.client import Auth


class NeuralMachineTranslationClient:
    """
    A class for translating text to text. Provides :meth:`translate` which returns translated text
    """
    def __init__(self, auth: Auth) -> None:
        """
        Initializes an instance of the class.

        Args:
            auth (:obj:`Auth`): an instance of :class:`riva.client.auth.Auth` which is used for authentication metadata
                generation.
        """
        self.auth = auth
        self.stub = riva_nmt_srv.RivaTranslationStub(self.auth.channel)

    def translate(
        self,
        texts: List[str],
        model: str,
        source_language: str,
        target_language: str,
        future: bool = False,
    ) -> Union[riva_nmt.TranslateTextResponse, _MultiThreadedRendezvous]:
        """
        Translate input list of input text :param:`text` using model :param:`model` from :param:`source_language` into :param:`target_language`

        Args:
            text (:obj:`list[str]`): input text.
            future (:obj:`bool`, defaults to :obj:`False`): whether to return an async result instead of usual
                response. You can get a response by calling ``result()`` method of the future object.

        Returns:
            :obj:`Union[riva.client.proto.riva_nmt_pb2.TranslateTextResponse, grpc._channel._MultiThreadedRendezvous]`:
            a response with output. You may find :class:`riva.client.proto.riva_nmt_pb2.TranslateTextResponse` fields
            description `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nmt-proto>`_.
        """
        req = riva_nmt.TranslateTextRequest(
            texts=texts,
            model=model,
            source_language=source_language,
            target_language=target_language
        )

        func = self.stub.TranslateText.future if future else self.stub.TranslateText
        return func(req, metadata=self.auth.get_auth_metadata())

    def get_config(
            self,
            model: str,
            future: bool = False,
    ) -> Union[riva_nmt.AvailableLanguageResponse, _MultiThreadedRendezvous]:
        req = riva_nmt.AvailableLanguageRequest(model=model)
        func = self.stub.ListSupportedLanguagePairs.future if future else self.stub.ListSupportedLanguagePairs
        return func(req, metadata=self.auth.get_auth_metadata())
