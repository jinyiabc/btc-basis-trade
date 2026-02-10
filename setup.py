#!/usr/bin/env python3
"""
BTC Basis Trade Analysis Toolkit - Package Setup

Install with: pip install -e .
"""

from setuptools import setup, find_packages

setup(
    name="btc-basis",
    version="1.0.0",
    description="Bitcoin Basis Trade Analysis Toolkit",
    author="BTC Basis Trade Toolkit",
    python_requires=">=3.8",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "requests>=2.31.0",
        "python-dateutil>=2.8.2",
    ],
    extras_require={
        "ibkr": ["ib-insync>=0.9.70"],
        "dev": ["pytest>=7.0.0"],
    },
    entry_points={
        "console_scripts": [
            "btc-basis=btc_basis.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
