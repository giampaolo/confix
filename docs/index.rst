.. module:: confix
   :synopsis: confix module
.. moduleauthor:: Giampaolo Rodola' <grodola@gmail.com>

confix documentation
====================

Quick links
-----------

* `Home page <https://github.com/giampaolo/confix>`__
* `Blog <http://grodola.blogspot.com/search/label/confix>`__
* `Forum <https://groups.google.com/forum/#!forum/python-confix>`__
* `Download <https://pypi.python.org/pypi?:action=display&name=confix#downloads>`__

About
-----

Confix is a language-agnostic configuration parser for Python.
It lets you define the default configuration of an app as a standard Python
class, then overwrite only the keys you need from a static config file (be it
YAML, JSON, INI or TOML) and/or via environment variables.
This is useful in order to avoid storing sensitive data (e.g. passwords) in the
source code.

confix is a relatively small library so this paper will try describe how to use
it mainly by using examples.
All the examples shown in this guide use YAML.

Usage by examples
=================

Override a key via conf file
----------------------------

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

config file:

.. code-block:: yaml

    # config.yml
    password: secret

shell:

.. code-block:: text

    $ python main.py
    ftp
    secret

Things to note:
 - ``password`` got changed by config file.
 - ``parse()`` did the trick.
 - configuration fields ("keys") can be accessed as ``config.name``.


Override a key via environment variable
---------------------------------------

python file:

.. code-block:: python

    # main.py
    from confix import register, parse_with_envvars

    @register()
    class config:
        username = 'ftp'
        password = None

    parse_with_envvars()
    print(config.username)
    print(config.password)

shell:

.. code-block:: text

    $ PASSWORD=secret python main.py
    ftp
    secret

Things to note:
 - env vars are case insensitive (to change this behavior you can use
   ``parse_with_envvars(case_sensitive=True))``.
 - we could have parsed the conf file as well with
   ``parse_with_envvars('config.yaml', case_sensitive=True))``.
 - env vars take precedence over config file though.

Errors - conf definition
------------------------

One of the key features is that the config class is a definition of all your
app configuration. If the conf file declares a key which is not defined in the
config class confix will error out.

.. code-block:: python

    # main.py
    from confix import register, parse

    @register()
    class config:
        username = 'ftp'
        password = None

    parse()

config file:

.. code-block:: yaml

    # config.yml
    host: localhost

shell:

.. code-block:: text

    $ python main.py
    Traceback (most recent call last):
      File "main.py", line 9, in <module>
        parse('config.yaml')
      File "/home/giampaolo/svn/confix/confix.py", line 473, in parse
        type_check=type_check)
      File "/home/giampaolo/svn/confix/confix.py", line 289, in __init__
        self.process_conf(conf)
      File "/home/giampaolo/svn/confix/confix.py", line 378, in process_conf
        section=None)
      File "/home/giampaolo/svn/confix/confix.py", line 393, in process_pair
        raise UnrecognizedKeyError(key, new_value, section=section)
    confix.UnrecognizedKeyError: config file provides key 'host' with value 'localhost' but key 'host' is not defined in the config class


Errors - types check
--------------------

Each key in the config class (may) have a default value. By default confix will
raise an exception if the value overwritten by the config file (or env var) has
a different type. This can be disabled with
``parse('config.yaml', type_check=False)``.

python file:

.. code-block:: python

    # main.py
    from confix import register, parse

    @register()
    class config:
        host = 'localhost'
        port = 80

    parse('config.yaml')

config file:

.. code-block:: yaml

    # config.yml
    host: 10.0.0.1
    port: foo

shell:

.. code-block:: text

    $ python main.py
    Traceback (most recent call last):
      File "main.py", line 9, in <module>
        parse('config.yaml')
      File "/home/giampaolo/svn/confix/confix.py", line 473, in parse
        type_check=type_check)
      File "/home/giampaolo/svn/confix/confix.py", line 289, in __init__
        self.process_conf(conf)
      File "/home/giampaolo/svn/confix/confix.py", line 378, in process_conf
        section=None)
      File "/home/giampaolo/svn/confix/confix.py", line 415, in process_pair
        section=section)
    confix.TypesMismatchError: type mismatch for key 'port' (default_value=80) got 'foo'


Required arguments
------------------

You can force certain arguments to be required, meaning they **have** to be
specified via conf file or environment variable.

python file:

.. code-block:: python

    # main.py
    from confix import register, parse_with_envvars, schema

    @register()
    class config:
        username = 'ftp'
        password = schema(None, required=True)

    parse_with_envvars('config.yaml')
    print(config.password)

config file:

.. code-block:: yaml

    # config.yml

shell:

.. code-block:: text

    $ python main.py
    Traceback (most recent call last):
      File "main.py", line 9, in <module>
        parse_with_envvars('config.yaml')
      File "/home/giampaolo/svn/confix/confix.py", line 501, in parse_with_envvars
        envvar_parser=envvar_parser)
      File "/home/giampaolo/svn/confix/confix.py", line 291, in __init__
        self.process_conf(conf)
      File "/home/giampaolo/svn/confix/confix.py", line 382, in process_conf
        self.run_last_schemas()
      File "/home/giampaolo/svn/confix/confix.py", line 449, in run_last_schemas
        raise RequiredKeyError(key, section=section)
    confix.RequiredKeyError: configuration class requires 'password' key to be specified via config file or env var
    $
    $ PASSWORD=secret python main.py
    secret

Validators
----------

A validator is function which is called to validate the value overridden by the
config file (or env var). If the function returns ``False`` or raise
``confix.ValidationError`` the validation will fail.
In this example we provide a validator which checks the password length.
Also, it's ``required``.

python file:

.. code-block:: python

    # main.py
    from confix import register, parse_with_envvars, schema

    @register()
    class config:
        username = 'ftp'
        password = schema(None, required=True, validator=lambda x: len(x) => 6)

    parse_with_envvars()
    print(config.password)

shell:

.. code-block:: text

    $ PASSWORD=foo python main.py
    Traceback (most recent call last):
      File "main.py", line 9, in <module>
        parse_with_envvars()
      File "/home/giampaolo/svn/confix/confix.py", line 501, in parse_with_envvars
        envvar_parser=envvar_parser)
      File "/home/giampaolo/svn/confix/confix.py", line 291, in __init__
        self.process_conf(conf)
      File "/home/giampaolo/svn/confix/confix.py", line 380, in process_conf
        section=None)
      File "/home/giampaolo/svn/confix/confix.py", line 434, in process_pair
        raise exc
    confix.ValidationError: 'password' key with value 'foo' didn't pass validation
    $
    $ PASSWORD=longpassword python main.py
    longpassword

A more advanced validator may look like this:

.. code-block:: python

    # main.py
    from confix import register, parse_with_envvars, schema, ValidationError

    def validate_password(value):
        if len(value) < 6:
            raise ValidationError("password is too short (< 6 chars)")
        elif value in ("password", "123456"):
            raise ValidationError("password is too fragile")
        return True

    @register()
    class config:
        username = 'ftp'
        password = schema(None, required=True, validator=validate_password)

    parse_with_envvars()
    print(config.password)


Multiple configuration classes
==============================

You may want to do this in case you have an app with different components and
you want to control everything from a single config file having different
sections.
Example:

python file:

.. code-block:: python

    # main.py
    from confix import register, parse

    @register()
    class config:
        debug = False

    @register(section='ftp')
    class ftp_config:
        port = 21
        username = 'ftp'

    @register(section='http')
    class http_config:
        port = 80
        username = 'www'

    parse('config.yaml')
    print(ftp_config.port)
    print(ftp_config.username)
    print(http_config.port)
    print(http_config.username)

config file:

.. code-block:: yaml

    # config.yml
    ftp:
        username: ftp-custom
    http:
        username: http-custom

shell:

.. code-block:: text

    $ python main.py
    21
    ftp-custom
    80
    http-custom


Things to note:
 - if we would have used ``parse_with_envvars()`` and specified a ``USERNAME``
   env var via cmdline ``username`` key of both config classes would have been
   overwritten.
 - we may also have defined a third "root" config class, with no section.
