from setuptools import setup, find_packages

setup(
    name="tariff-query",
    version="1.0.0",
    packages=find_packages(include=['src', 'src.*']),
    install_requires=[
        'aiohttp>=3.8.5',
        'beautifulsoup4>=4.12.0',
        'requests>=2.31.0',
        'pandas>=2.0.0',
        'openpyxl>=3.1.2',
        'python-Levenshtein>=0.21.1',
    ],
    python_requires='>=3.10',
    entry_points={
        'console_scripts': [
            'tariff-query=src.main:main',
        ],
    },
)