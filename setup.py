#
# Copyright 2016 University of Southern California
# Distributed under the Apache License, Version 2.0. See LICENSE for more info.
#

""" Installation script for the ioboxd web service.
"""

from setuptools import setup, find_packages

setup(
    name='ioboxd',
    description='REST Web Service Interface for DERIVA data export',
    url='https://github.com/informatics-isi-edu/ioboxd',
    maintainer='USC Information Sciences Institute ISR Division',
    maintainer_email='misd-support@isi.edu',
    version="0.3.4",
    zip_safe=False,
    packages=find_packages(),
    scripts=["bin/ioboxd-deploy", "bin/ioboxd-prune"],
    package_data={'ioboxd': ["*.wsgi"]},
    data_files=[
        ('share/ioboxd', [
            "conf/wsgi_ioboxd.conf",
        ]),
        ('share/ioboxd', [
            "conf/ioboxd_config.json",
        ])
    ],
    requires=[
        'os',
        'sys',
        'platform',
        'logging',
        'mimetypes',
        'shutil',
        'tempfile',
        'urlparse',
        'simplejson',
        'ordereddict',
        'requests',
        'certifi',
        "web.py",
        "psycopg2",
        "webauthn2",
        "deriva"],
    license='Apache 2.0',
    classifiers=[
        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        "Operating System :: POSIX",
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        "Topic :: Internet :: WWW/HTTP"
    ]
)

