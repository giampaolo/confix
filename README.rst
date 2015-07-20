.. image:: https://img.shields.io/pypi/dm/confix.svg
    :target: https://pypi.python.org/pypi/confix#downloads
    :alt: Downloads this month

.. image:: https://api.travis-ci.org/giampaolo/confix.png?branch=master
    :target: https://travis-ci.org/giampaolo/confix
    :alt: Linux tests (Travis)

.. image:: https://coveralls.io/repos/giampaolo/confix/badge.svg?branch=master&service=github
    :target: https://coveralls.io/github/giampaolo/confix?branch=master
    :alt: Test coverage (coverall.io)

.. image:: https://img.shields.io/pypi/v/confix.svg
    :target: https://pypi.python.org/pypi/confix/
    :alt: Latest version

.. image:: https://img.shields.io/pypi/l/confix.svg
    :target: https://pypi.python.org/pypi/confix/
    :alt: License

**Warning**: this is beta software and its API might be subject to change between versions

Confix
======

Quick links
-----------

* `Code and bug tracker <https://github.com/giampaolo/confix>`_
* `PYPI <https://pypi.python.org/pypi/confix>`_

About
-----

A language-agnostic configuration parser for Python.
It lets you define the default configuration of an app as a standard Python
class, then **overwrite only the keys you need** from a static config file
(be it **YAML, JSON or TOML**) and/or environment variables.
This is useful in order to avoid storing sensitive data (e.g. passwords) in
the source code.

Example using configuration file:

config file:

.. code-block:: yaml

    # config.yaml
    password: secret

python file:

.. code-block:: python

    # ftp.py
    from confix import register, parse

    @register()
    class config:
        host = 'localhost'
        port = 2121
        user = 'ftp'
        password = None         # this will be overridden later

    if __name__ == '__main__':
        parse('config.yaml')    # make replacements to "config" class
        print(config.user)      # will print "ftp"
        print(config.password)  # will print "secret" instead of None


...if you want to also parse environment variables (order of precedence:
env-vars -> config file -> config class):

python file:

.. code-block:: python

    # ftp.py
    from confix import register, parse_with_envvars

    @register()
    class config:
        host = 'localhost'
        port = 2121
        user = 'ftp'
        password = None         # this will be overridden later

    if __name__ == '__main__':
        parse_with_envvars()    # make replacements to "config" class
        print(config.user)      # will print "ftp"
        print(config.password)  # will print "secret" instead of None

from the shell:

.. code-block:: bash

    $ FOO=2 python ftp.py
    giampaolo
    secret

Main features
-------------

- supports **YAML, JSON** and **TOML** serialization formats.
- can be easily extended to support other formats.
- support for Python 3
- small code base
- allows you to define 'schemas' in order to **validate** options and mark them
  as **required**:

 .. code-block:: python

  # ftp.py
  from confix import register, schema

  @register()
  class config:
      port = schema(default=21, validator=lambda x: isinstance(x, int))
      password = schema(required=True)

Status
------

Still beta.
