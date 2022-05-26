# Integration tests for Python Riva clients

These tests check functionality of scripts from `scripts` directory.
Before running the tests, you will need to start a Riva server. The simplest
way to do it is to use quick start scripts as described 
[here](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/quick-start-guide.html#local-deployment-using-quick-start-scripts).

If you set up Riva server at `localhost:50051`, then to run the tests use command from the repo root
```bash
bash tests/integration/launch_all_scripts_testing.sh
```

If your server address is different you will need to set `SERVER` environment variable.
```bash
SERVER=YOUR_SERVER_ADDRESS_AND_PORT bash tests/integration/launch_all_scripts_testing.sh
```

For using SSL during testing, please provide path to SSL certificate in `SSL_CERT` variable or set
`USE_SSL` to `1`.

You may run tests only for one service, e.g. ASR:
```bash
bash tests/integration/asr.sh
```
or tests for a specific script:
```bash
bash tests/integration/tts/test_talk.sh
```

Outputs created during testing as well STDOUT and STDERR are saved to
directories `tests/integration/asr/outputs`, `tests/integration/nlp/outputs`,
`tests/integration/tts/outputs`.
