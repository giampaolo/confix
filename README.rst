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

* `Home page <https://github.com/giampaolo/confix>`__
* `Blog <http://grodola.blogspot.com/search/label/confix>`__
* `Forum <https://groups.google.com/forum/#!forum/python-confix>`__
* `Download <https://pypi.python.org/pypi?:action=display&name=confix#downloads>`__

About
-----

A language-agnostic configuration parser for Python.
It lets you define the default configuration of an app as a standard Python
class, then **overwrite only the keys you need** from a static config file
(be it **YAML, JSON, INI or TOML**) and/or
`environment variables <http://pythonhosted.org/confix#override-a-key-via-environment-variable>`_.
This is useful in order to avoid storing sensitive data (e.g. passwords) in
the source code.

Example:

python file:

.. code-block:: python

    # main.py
    from confix import register, parse

    @register()
    class config:
        username = 'ftp'
        password = None     # this will be overridden by the conf file

    parse('config.yaml')    # make replacements to "config" class
    print(config.username)  # will print "ftp"
    print(config.password)  # will print "secret" instead of None

config file:

.. code-block:: yaml

    # config.yml
    password: secret

shell:

.. code-block:: bash

    $ python main.py
    ftp
    secret

For more examples see `docs <http://pythonhosted.org/confix>`_.

Main features
-------------

- supports **YAML, JSON**, **INI** and **TOML** serialization formats.
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

Still beta, especially ini file support.
