export const VERSION = {
    MAJOR: 2,
    MINOR: 18,
    PATCH: 0,
    PRE_RELEASE: 'rc0'
} as const;

export const PACKAGE_INFO = {
    shortversion: `${VERSION.MAJOR}.${VERSION.MINOR}.${VERSION.PATCH}`,
    version: `${VERSION.MAJOR}.${VERSION.MINOR}.${VERSION.PATCH}${VERSION.PRE_RELEASE}`,
    packageName: 'nvidia-riva-client',
    contactNames: 'Anton Peganov',
    contactEmails: 'apeganov@nvidia.com',
    homepage: 'https://github.com/nvidia-riva/python-clients',
    repositoryUrl: 'https://github.com/nvidia-riva/python-clients',
    downloadUrl: 'https://github.com/nvidia-riva/python-clients/releases',
    description: 'TypeScript implementation of the Riva Client API',
    license: 'MIT',
    keywords: [
        'deep learning',
        'machine learning',
        'gpu',
        'NLP',
        'ASR',
        'TTS',
        'NMT',
        'nvidia',
        'speech',
        'language',
        'Riva',
        'client'
    ],
    rivaVersion: '2.18.0',
    rivaRelease: '24.12',
    rivaModelsVersion: '2.18.0'
} as const;
