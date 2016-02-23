.. image:: https://img.shields.io/pypi/dm/confix.svg
    :target: https://pypi.python.org/pypi/confix#downloads
    :alt: Downloads this month

.. image:: https://api.travis-ci.org/giampaolo/confix.png?branch=master
    :target: https://travis-ci.org/giampaolo/confix
    :alt: Linux tests (Travis)

.. image:: https://ci.appveyor.com/api/projects/status/kmkc7f7muvrcr8oq?svg=true
    :target: https://ci.appveyor.com/project/giampaolo/confix
    :alt: Windows tests (Appveyor)

.. image:: https://coveralls.io/repos/giampaolo/confix/badge.svg?branch=master&service=github
    :target: https://coveralls.io/github/giampaolo/confix?branch=master
    :alt: Test coverage (coverall.io)

.. image:: https://img.shields.io/pypi/v/confix.svg
    :target: https://pypi.python.org/pypi/confix/
    :alt: Latest version

.. image:: https://img.shields.io/pypi/l/confix.svg
    :target: https://pypi.python.org/pypi/confix/
    :alt: License

Confix
======

Quick links
-----------

* `Home page <https://github.com/giampaolo/confix>`__
* `Documentation <http://pythonhosted.org/confix/>`__
* `Blog <http://grodola.blogspot.com/search/label/confix>`__
* `Forum <https://groups.google.com/forum/#!forum/python-confix>`__
* `Download <https://pypi.python.org/pypi?:action=display&name=confix#downloads>`__

About
-----

Confix is a language-agnostic configuration parser for Python.
It lets you define the default configuration of an app as a standard Python
class, then overwrite its attributes from a static configuration file (be it
YAML, JSON, INI or TOML) and / or via
`environment variables <http://pythonhosted.org/confix/#override-a-key-via-environment-variables>`_.
In doing so it validates the overridden settings by:

- making sure they are of the same type
- (optional) marking them as mandatory (useful for passwords)
- (optional) validating them via a callable

Example:

config file:

.. code-block:: yaml

    # config.yml
    password: secret

python file:

.. code-block:: python

    # main.py
    from confix import register, parse

    @register()
    class config:
        username = 'ftp'
        password = None

    parse('config.yaml')
    print(config.username)
    print(config.password)

shell:

.. code-block:: bash

    $ python main.py
    ftp
    secret

For more examples see `docs <http://pythonhosted.org/confix>`_.

Main features
-------------

- supports **YAML**, **JSON**, **INI** and **TOML** serialization formats.
- can be easily extended to support other formats.
- support for Python 3
- small code base
- 100% test coverage
- allows you to define 'schemas' in order to **validate** fields and mark them
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

Code is solid and fully tested (100% coverage). Its API may change (break)
between major versions though.
