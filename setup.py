#!/usr/bin/env python3
"""Setup modules and dependencies"""
from setuptools import setup

setup(
    name='LookPyrenees',
    package_dir = {"": "src"},
    packages=['LookPyrenees'],
    version='0.0.1',
    author='Romain Buguet de Chargère',
    author_email='rbuguet@gmail.com',
    description='Downloading and visualize snow condition in pyrenees',
    install_requires=[
        'earthpy==0.9.4',
        'eodag==2.10.0',
        'fire==0.4.0',
        'folium==0.14.0',
        'geopandas>=0.9.0',
        'matplotlib==3.7.1',
        'pandas==1.4.4',
        'python-dateutil<2.9',
        'protobuf==3.20.0',
        'rasterio==1.3.6',
        'requests<3',
        'rioxarray==0.13.4',
        'scipy==1.9.1',
        'Shapely==2.0.1',
        'tqdm==4.64.1',
        'urllib3==1.25.8',
        'xarray==2023.1.0',
    ],
    entry_points={
        "console_scripts": [
            "LookPyrenees = LookPyrenees.cli:run",
        ]
    },
) 
# packages=find_packages(),
# include_package_data=True,
