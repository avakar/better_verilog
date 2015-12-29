#!/usr/bin/env python
# coding: utf-8

from setuptools import setup

setup(
    name='better_verilog',
    version='0.1',

    description='A translactor from better_verilog HDL to pure verilog.',
    author='Martin Vejnár',
    author_email='avakar@ratatanek.cz',
    url='https://github.com/avakar/better_verilog',
    license='MIT',

    packages=['better_verilog'],
    install_requires=['speg'],
    entry_points = {
        'console_scripts': [
            'bv = better_verilog.__main__:main'
        ],
    }
)
