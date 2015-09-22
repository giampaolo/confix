#!/bin/bash

set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    brew update || brew update
    brew outdated pyenv || brew upgrade pyenv
    brew install pyenv-virtualenv

    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi

    case "${PYVER}" in
        py26)
            pyenv install 2.6.9
            pyenv virtualenv 2.6.9 confix
            ;;
        py27)
            pyenv install 2.7.10
            pyenv virtualenv 2.7.10 confix
            ;;
        py33)
            pyenv install 3.3.6
            pyenv virtualenv 3.3.6 confix
            ;;
        py34)
            pyenv install 3.4.3
            pyenv virtualenv 3.4.3 confix
            ;;
    esac
    pyenv rehash
    pyenv activate confix
fi

pip install coverage coveralls flake8 pep8 pyyaml toml pytest pytest-cov

if [[ $TRAVIS_PYTHON_VERSION == '2.6' ]] || [[ $PYVER == 'py26' ]]; then
    pip install -U unittest2 ipaddress
elif [[ $TRAVIS_PYTHON_VERSION < '3.3' ]] || [[ $PYVER < 'py33' ]]; then
    pip install -U ipaddress
elif [[ $TRAVIS_PYTHON_VERSION == 'pypy' ]] || [[ $PYVER == 'pypy' ]]; then
    pip install -U ipaddress
fi
