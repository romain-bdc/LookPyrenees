#!/usr/bin/env python3

from setuptools import setup
from src.obs_pyr.__init__ import version
setup(
    name='LookPyrenees',
    version=version,
    author='Romain Buguet de Chargère',
    author_email='rbuguet@gmail.com',
    description='Downloading and visualize snow condition in pyrenees',

    install_requires=[
        'earthpy==0.9.4',
        'eodag==2.10.0',
        'fire==0.4.0',
        'geopandas==0.12.2',
        'matplotlib==3.7.1',
        'numpy==1.24.2',
        'pandas==2.0.0',
        'python-dateutil<2.9',
        'protobuf==3.20.0',
        'rasterio==1.3.6',
        'requests<3',
        'rioxarray==0.9.4',
        'scipy==1.9.1',
        'Shapely==2.0.1',
        'tqdm==4.64.1',
        'xarray==2023.1.0',
    ],
    # test_suite='tests',
    # package_dir={'': 'src'},
    # packages=find_packages('src'),
    # entry_points={
    #     'console_scripts': [
    #         'worldcereal=worldcereal.__main__:main'
    #     ]
    # }
)