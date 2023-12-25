#!/usr/bin/env python3
"""Setup modules and dependencies"""
from setuptools import setup

setup(
    name="LookPyrenees",
    package_dir={"": "src"},
    packages=["LookPyrenees"],
    version="0.0.1",
    author="Romain Buguet de Chargère",
    author_email="rbuguet@gmail.com",
    description="Downloading and visualize snow condition in pyrenees",
    install_requires=[
        "pre-commit",
    ],
    entry_points={
        "console_scripts": [
            "LookPyrenees = LookPyrenees.cli:run",
        ]
    },
)
