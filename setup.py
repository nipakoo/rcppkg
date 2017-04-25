#!/usr/bin/python

from setuptools import setup, find_packages

setup(
    name="rcppkg",
    version="0.3",
    author="Niko Kortstrom",
    author_email="niko.kortstrom@nokia.com",
    description=("RCP plugin to rpkg to manage package spec files in a git repository"),
    license="GPLv2+",
    url="https://github.com/nipakoo/rcppkg.git",
    packages=find_packages(),
    scripts=['bin/rcppkg'],
    data_files=[('/etc/bash_completion.d', ['etc/bash_completion.d/rcppkg.bash']),
                ('/etc/rpkg', ['etc/rpkg/rcppkg.conf'])],
    install_requires=[
            'GitPython',
            'wget',
            'python-gitlab',
            'HTMLParser',
            'ndg-httpsclient',
            'requests'
    ]
)
