.. module:: confix
   :synopsis: confix module
.. moduleauthor:: Giampaolo Rodola' <grodola@gmail.com>

.. warning::

   This documentation refers to latest GIT version of confix which has not been
   released yet.

confix documentation
====================

Quick links
-----------

* `Home page <https://github.com/giampaolo/confix>`__
* `Blog <http://grodola.blogspot.com/search/label/confix>`__
* `Forum <https://groups.google.com/forum/#!forum/python-confix>`__
* `Download <https://pypi.python.org/pypi?:action=display&name=confix#downloads>`__

About
=====

Confix is a language-agnostic configuration parser for Python.
It lets you define the default configuration of an app as a standard Python
class, then overwrite only the keys you need from a static config file (be it
YAML, JSON, INI or TOML) and/or via environment variables.
This is useful in order to avoid storing sensitive data (e.g. passwords) in the
source code.

API reference
=============

**Exceptions**

.. class:: ValidationError(msg)

    Raised when a :func:`confix.schema()` validation fails.
    You can define a custom validator and have it raise this exception instead
    of returning False in order to provide a custom error message.

.. class:: NotParsedError(msg)

    Called when :func:`get_parsed_conf()` is called but :func:`confix.parse()`
    has not been called yet.

**Functions**

.. function:: confix.register(section=None)

    A decorator which registers a configuration class which will be parsed
    later.
    If *section* is ``None`` it is assumed that the configuration file will not
    be split in sub-sections otherwise *section* is the name of a specific
    section which will be referenced by the config file.
    All class attributes starting with an underscore will be ignored, same
    for methods, classmethods or any other non-callable type.
    A class decoratored with this method becomes dict()-able.
    Keys can be accessed as normal attributes or also as a dict.

    .. code-block:: python

        >>> import confix
        >>>
        >>> @confix.register()
        >>> class config:
        ...     foo = 1
        ...     bar = 2
        ...
        >>> config.foo
        1
        >>> config['foo']
        1
        >>> dict(config)
        {'foo': 1, 'bar': 2}

.. function:: schema(default=_DEFAULT, required=False, validator=None)

    A schema can be used to validate configuration key's values or state they
    are mandatory.
    *default* is the default key value.
    If *required* is ``True`` it is mandatory for the config file (or the
    env var) to specify that key.
    *validator* is a function or a list of functions which will be called for
    validating the overridden value.
    A validator function will fail if it returns ``False`` or raise
    :class:`ValidationError`.

.. function:: confix.parse(conf_file=None, file_parser=None, type_check=True)

    Parse configuration class(es) replacing values if a configuration file
    is provided.
    *conf_file* is a path to a configuration file or an existing
    file-like object. If this is ``None`` configuration class will be parsed
    anyway in order to validate its :func:`confix.schema()` s.
    *file_parser* is a callable parsing the configuration file and
    converting it to a dict.  If ``None`` a default parser will be
    picked up depending on the file extension. You may want to override this
    either to support new file extensions or types.
    If *type_check* is `True` `TypesMismatchError` will be raised in case an
    an option specified in the configuration file has a different type than the
    one defined in the configuration class.

.. function:: confix.parse_with_envvars(conf_file=None, file_parser=None, type_check=True, case_sensitive=False, envvar_parser=None)

    Same as :func:`confix.parse()` but also takes environment variables into
    account.
    If an environment variable name matches a key of the config class that
    will replaced with the environment variable value which will be converted
    by *envvar_parser* function first.
    If *case_sensitive* is ``False`` env var ``"FOO"`` and ``"foo"`` will be
    the treated the same and will override config class' key ``"foo"``.
    *envvar_parser* is the callable which converts the environment variable
    value (which is always a string) based on the default value type defined
    in the config class (e.g. if ``config.foo`` is a float the environment
    variable value will be casted to a float.
    If *conf_file* is specified also a configuration file will be parsed but
    the environment variables will take precedence as in:
    ``environment variable -> config file -> config class default value``.

.. function:: get_parsed_conf()

    Return the whole parsed configuration as a dict.
    If :func:`confix.parse()` has not been called yet raise
    :class:`confix.NotParsedError`.

**Validators**

Validators are simple utility functions which can be used with
:func:`confix.schema()` s.

.. function:: istrue(value)

    Assert value evaluates to ``True``.

.. function:: isin(value, seq)

    Assert value is in a sequence.

.. function:: isnotin(value, seq)

    Assert value is not in a sequence.

.. function:: isemail(value)

    Assert value is a valid email.

Usage by examples
=================

Override a key via configuration file
-------------------------------------

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
 - parse_with_envvars
   ``parse_with_envvars('config.yaml', case_sensitive=True))``.
 - env vars take precedence over config file though.

Errors: configuration definition
--------------------------------

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


Errors: types checking
----------------------

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

You can force certain arguments to be required, meaning they *have* to be
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
