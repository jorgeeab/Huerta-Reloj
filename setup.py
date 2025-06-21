from setuptools import setup, find_packages

setup(
    name='basic_gym_env',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'gym',
        'numpy',
    ],
)
