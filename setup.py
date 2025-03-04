from setuptools import setup, find_packages

setup(
    name="tariff-query",
    version="1.0.0",
    packages=find_packages(include=['src', 'src.*']),
    install_requires=[
        'aiohttp>=3.8.5',
        'beautifulsoup4>=4.12.2',
        'requests>=2.31.0',
        'python-Levenshtein>=0.21.1',
        'jellyfish>=1.0.1',
        'numpy>=1.24.3',
        'pandas>=1.5.3',
        'openpyxl>=3.1.2',
    ],
    entry_points={
        'console_scripts': [
            'tariff-query=src.main:main',
        ],
    },
)