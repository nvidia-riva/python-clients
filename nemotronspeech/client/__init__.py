# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

from nemotronspeech.client.asr import (
    AudioChunkFileIterator,
    ASRService,
    add_audio_file_specs_to_config,
    add_word_boosting_to_config,
    add_speaker_diarization_to_config,
    get_wav_file_parameters,
    print_offline,
    print_streaming,
    sleep_audio_length,
    add_endpoint_parameters_to_config,
    add_custom_configuration_to_config,
)
from nemotronspeech.client.auth import Auth
from nemotronspeech.client.nlp import (
    NLPService,
    extract_all_text_classes_and_confidences,
    extract_all_token_classification_predictions,
    extract_most_probable_text_class_and_confidence,
    extract_most_probable_token_classification_predictions,
)
from nemotronspeech.client.package_info import (
    __contact_emails__,
    __contact_names__,
    __description__,
    __download_url__,
    __homepage__,
    __keywords__,
    __license__,
    __package_name__,
    __repository_url__,
    __shortversion__,
    __version__,
)
from nemotronspeech.client.proto.nemotron_asr_pb2 import RecognitionConfig, StreamingRecognitionConfig, EndpointingConfig
from nemotronspeech.client.proto.nemotron_audio_pb2 import AudioEncoding
from nemotronspeech.client.proto.nemotron_nlp_pb2 import AnalyzeIntentOptions
from nemotronspeech.client.proto.nemotron_nmt_pb2 import StreamingTranslateSpeechToSpeechConfig, TranslationConfig, SynthesizeSpeechConfig, StreamingTranslateSpeechToTextConfig
from nemotronspeech.client.tts import SpeechSynthesisService
from nemotronspeech.client.nmt import NeuralMachineTranslationClient
