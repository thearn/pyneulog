
from setuptools import setup, find_packages

setup(name='pyneulog',
    version='0.1',
    install_requires=['pyserial'],
    description="Python interface for Neulog GSR sensors",
    author='Tristan Hearn',
    author_email='tristanhearn@gmail.com',
    url='https://github.com/thearn/pygsr',
    license='Apache 2.0',
    packages=['neulog'],
)
