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
(be it **YAML, JSON, INI or TOML**).
This is useful in order to avoid storing sensitive data (e.g. passwords) in
the source code.

Example:

config file:

.. code-block:: yaml

    # config.yaml
    ftp:
        password: secret

python file:

.. code-block:: python

    # ftp.py
    from confix import register, parse

    @register('ftp')
    class config:
        host = 'localhost'
        port = 2121
        user = 'ftp'
        password = None         # this will be overridden later

    if __name__ == '__main__':
        parse('config.yaml')    # make replacements to "config" class
        print(config.user)      # will print "ftp"
        print(config.password)  # will print "secret"

Additional features
-------------------

- supports **YAML, JSON, INI** and **TOML** serialization formats.
- can be easily extended to support other formats.
- support for Python 3
- small code base
- allows you to define 'schemas' in order to **validate** options and mark them
  as **required**:

 .. code-block:: python

  # ftp.py
  from confix import register, schema

  @register('ftp')
  class config:
      port = schema(default=21, validator=lambda x: isinstance(x, int))
      password = schema(required=True)

Status
------

Still beta, but the base API/functionality will likely remain unmodified.
