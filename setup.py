import sys
from setuptools import setup

if sys.version_info < (2, 6):
    sys.exit('python >= 2.6 only')

setup(
    name='confix',
    version='0.1.0',
    description='Language agnostic configuration parser',
    license='License :: OSI Approved :: MIT License',
    platforms='Platform Independent',
    author="Giampaolo Rodola'",
    author_email='g.rodola@gmail.com',
    url='https://pypi.python.org/pypi/confix',
    py_modules=['confix'],
    keywords=['config', 'yaml', 'toml', 'json', 'ini', 'sensitive',
              'password'],
    # ...supposed to be installed by user if needed
    #install_requires=['PyYAML', 'toml']
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.0',
        'Programming Language :: Python :: 3.1',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python',
        'Topic :: Security',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Libraries',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',
    ],
)
