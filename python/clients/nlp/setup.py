from setuptools import Extension, setup

install_requirements = ["numpy", "sklearn"]

packages = ["riva_nlp", "riva_nlp.cli"]

setup(
    description="Riva NLP Library & CLI",
    author="Ryan Leary",
    author_email="rleary@nvidia.com",
    version="0.1",
    install_requires=install_requirements,
    packages=packages,
    name="riva_nlp",
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "riva-nlp = riva_nlp.cli:interactive_main",
            "riva-nlp-eval = riva_nlp.cli:eval_main",
            "riva-nlp-punct = riva_nlp.cli:interactive_punct",
        ]
    },
)
