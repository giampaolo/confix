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
=====

Confix is a language-agnostic configuration parser for Python.
It lets you define the default configuration of an app as a standard Python
class, then overwrite its attributes from a static configuration file (be it
YAML, JSON, INI or TOML) and / or via
`environment variables <#override-a-key-via-environment-variable>`_.
This is useful to avoid storing sensitive data (e.g. passwords) in the source
code and validate configuration on startup (via validators, mandatory
attributes and type checking).

API reference
=============

**Exceptions**

.. class:: Error(msg)

    Base exception class from which derive all others.

.. class:: ValidationError(msg)

    Raised when a :func:`confix.schema()` validation fails.
    You can define a custom validator and have it raise this exception instead
    of returning False in order to provide a custom error message.

.. class:: NotParsedError(msg)

    Called when :func:`get_parsed_conf()` is called but :func:`confix.parse()`
    has not been called yet.

.. class:: AlreadyParsedError

    Raised when :func:`confix.parse()` or :func:`confix.parse_with_envvars()`
    is called twice.

.. class:: AlreadyRegisteredError

    Raised by :func:`confix.register` when registering the same section twice.

.. class:: NotParsedError

    Raised when :func:`confix.get_parsed_conf()` is called but
    :func:`confix.parse() has not been called yet.

.. class:: UnrecognizedSettingKeyError

    Raised on parse if the configuration file defines a setting key which is
    not defined by the default configuration class.
    You're not supposed to catch this but instead fix the configuration file.

.. class:: RequiredSettingKeyError

    Raised when the configuration file doesn't specify a setting key which was required
    via ``schema(required=True)``.
    You're not supposed to catch this but instead fix the configuration file.

.. class:: TypesMismatchError

    Raised when configuration file overrides a setting key having a type which is
    different than the original one defined in the configuration class.
    You're not supposed to catch this but instead fix the configuration file.

**Functions**

.. function:: confix.register(section=None)

    A decorator which registers a configuration class which will be parsed
    later.
    If *section* is ``None`` it is assumed that the configuration file will not
    be split in sub-sections otherwise *section* is the name of a specific
    section which will be referenced by the configuration file.
    All class attributes starting with an underscore will be ignored, same
    for methods, classmethods or any other non-callable type.
    A class decoratored with this method becomes dict()-able.
    Keys can be accessed as normal attributes or also as a dict.
    All attribute names starting with an underscore will be ignored.
    The class can also define classmethods.

.. function:: schema(default=_DEFAULT, required=False, validator=None, type_check=True)

    A schema can be used to validate configuration key's values or state they
    are mandatory.
    *default* is the default setting key value.
    If *required* is ``True`` it is mandatory for the configuration file (or
    the environment variable) to specify that key.
    *validator* is a function or a list of functions which will be called for
    validating the overridden value.
    A validator function will fail if it returns ``False`` or raise
    :class:`ValidationError`.
    *type_check* parameter overrides :func:`confix.parse()`'s type check
    parameter for this schema only; if ``True`` it will perform a type check
    against config file value type and schema's default type and error out if
    the two types are different.

    .. versionchanged:: 0.2.2 added *type_check* parameter.

.. function:: confix.parse(conf_file=None, file_parser=None, type_check=True)

    Parse configuration class(es) replacing values if a configuration file
    is provided.
    *conf_file* is a path to a configuration file or an existing
    file-like object. If *conf_file* is ``None`` configuration class will be
    parsed anyway in order to validate its schemas (:func:`confix.schema()`).
    *file_parser* is a callable parsing the configuration file and
    converting it to a dict.  If ``None`` a default parser will be
    picked up depending on the file extension. You may want to override this
    either to support new file extensions or types.
    If *type_check* is `True` `TypesMismatchError` will be raised in case an
    an option specified in the configuration file has a different type than the
    one defined in the configuration class.

.. function:: confix.parse_with_envvars(conf_file=None, file_parser=None, type_check=True, case_sensitive=False)

    Same as :func:`confix.parse()` but also takes environment variables into
    account.
    It must be noted that environment variables take precedence over the
    configuration file (if specified).
    Only upper cased environment variables are taken into account.
    By default (``case_sensitive=False``) environment variable ``"FOO"`` will override a setting key with the same name in a non case sensitive fashion
    (``'foo'``, ``'Foo'``, ``'FOO'``, etc.).
    Also multiple "sections" are not supported so if multiple config classes
    define a setting key ``'foo'`` all of them will be overwritten.
    If *case_sensitive* is ``True`` then it is supposed that the config
    class(es) define all upper cased keys.

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

.. function:: isurl(value)

    Assert value is a valid url. This includes urls starting with "http" and
    "https", IPv4 urls (e.g. "http://127.0.0.1") and optional port (e.g.
    "http://localhost:8080").

.. function:: isip4(value)

    Assert value is a valid IPv4 address.

.. function:: isip6(value)

    Assert value is a valid IPv6 address. On python < 3.3 requires
    `ipaddress <https://pypi.python.org/pypi/ipaddress>`_ module to be
    installed.

.. function:: isip46(value)

    Assert value is a valid IPv4 or IPv6 address. On python < 3.3 requires
    `ipaddress <https://pypi.python.org/pypi/ipaddress>`_ module to be
    installed.


Usage by examples
=================

Override a setting key via configuration file
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

configuration file:

.. code-block:: yaml

    # config.yml
    password: secret

shell:

.. code-block:: text

    $ python main.py
    ftp
    secret

Things to note:
- ``password`` got changed by configuration file.
- ``parse()`` did the trick.
- configuration fields ("keys") can be accessed as attributes
  (``config.name``).


Override a setting key via environment variables
------------------------------------------------

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
- ``"PASSWORD"`` environment variable changed the value of ``"password"``
  class attribute which is treated in a case insensitive fashion.
- to change this behavior use ``parse_with_envvars(case_sensitive=True))``
  but in that case also the class attributed must be upper case
  (``"PASSWORD"``).


Using configuration file and environment variables
--------------------------------------------------

You can overwrite default configuration by using both a configuration file
**and** environment variables. Environment variables take precedence over
the configuration file though.

python file:

.. code-block:: python

    # main.py
    from confix import register, parse_with_envvars

    @register()
    class config:
        username = 'ftp'
        password = None
        host = localhost

    parse_with_envvars(config_file='config.yml')
    print(config.username)
    print(config.password)
    print(config.host)

.. code-block:: yaml

    # config.yml
    username: john
    password: secret
    host: localhost

shell:

.. code-block:: text

    $ PASSWORD=somecrazypass python main.py
    john
    somecrazypass
    localhost

Things to note:
- ``"password"`` was specified in the configuration file but also by the
  environment variable and this takes precedence over the configuration file.


Errors: configuration definition
--------------------------------

One of the key features of confix is that the config class is a definition of
all your app configuration. If the configuration file declares a setting key
which is not defined in the config class confix will error out.
This is useful in case you made a typo in your configuration file: failing
sooner (application startup) rather than later is better.

.. code-block:: python

    # main.py
    from confix import register, parse

    @register()
    class config:
        username = 'ftp'
        password = None

    parse()

configuration file:

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
        raise UnrecognizedSettingKeyError(key, new_value, section=section)
    confix.UnrecognizedSettingKeyError: configuration file provides setting key 'host' with value 'localhost' but setting key 'host' is not defined in the config class

Things to note:
- setting key ``'host'`` was specified in the configuration file but not in the
  default config class.


Errors: types checking
----------------------

Each setting key in the config class (may) have a default value.
By default  confix will raise an exception if the value overwritten by the
configuration file (or environment variable) has a different type. This can be
disabled with ``parse('config.yaml', type_check=False)``.

python file:

.. code-block:: python

    # main.py
    from confix import register, parse

    @register()
    class config:
        host = 'localhost'
        port = 80

    parse('config.yaml')

configuration file:

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
    confix.TypesMismatchError: type mismatch for setting key 'port' (default_value=80) got 'foo'


Required arguments
------------------

You can force certain arguments to be required, meaning they *have* to be
specified via configuration file or environment variable.

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

configuration file:

.. code-block:: yaml

    # config.yml

shell:

.. code-block:: text

    $ python main.py
    Traceback (most recent call last):
      File "main.py", line 9, in <module>
        parse_with_envvars('config.yaml')
      File "/home/giampaolo/svn/confix/confix.py", line 501, in parse_with_envvars
        envvar_case_sensitive=case_sensitive)
      File "/home/giampaolo/svn/confix/confix.py", line 291, in __init__
        self.process_conf(conf)
      File "/home/giampaolo/svn/confix/confix.py", line 382, in process_conf
        self.run_last_schemas()
      File "/home/giampaolo/svn/confix/confix.py", line 449, in run_last_schemas
        raise RequiredKeyError(key, section=section)
    confix.RequiredKeyError: configuration class requires 'password' setting key to be specified via configuration file or environment variable
    $
    $ PASSWORD=secret python main.py
    secret


Validators
----------

A validator is function which is called to validate the value overridden by the
configuration file (or environment variable). If the function returns ``False``
or raise ``confix.ValidationError`` the validation will fail.
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
        envvar_case_sensitive=case_sensitive)
      File "/home/giampaolo/svn/confix/confix.py", line 291, in __init__
        self.process_conf(conf)
      File "/home/giampaolo/svn/confix/confix.py", line 380, in process_conf
        section=None)
      File "/home/giampaolo/svn/confix/confix.py", line 434, in process_pair
        raise exc
    confix.ValidationError: 'password' setting key with value 'foo' didn't pass validation
    $
    $ PASSWORD=longpassword python main.py
    longpassword


Marking keys as mandatory
-------------------------

Certain keys can be marked as mandatory, meaning if they are not specified in
the configuration file (or via environment variable) confix will error out.
This is useful to avoid storing sensitive data (e.g. passwords) in the source
code.

.. code-block:: python

    # main.py
    from confix import register, schema, parse

    @register()
    class config:
        password = schema(None, required=True)

    parse()

.. code-block:: text

    $ python main.py
    Traceback (most recent call last):
      File "main.py", line 7, in <module>
        parse()
      File "/home/giampaolo/svn/confix/confix.py", line 693, in parse
        type_check=type_check)
      File "/home/giampaolo/svn/confix/confix.py", line 443, in __init__
        self.process_conf(self.new_conf)
      File "/home/giampaolo/svn/confix/confix.py", line 574, in process_conf
        self.run_last_schemas()
      File "/home/giampaolo/svn/confix/confix.py", line 664, in run_last_schemas
        raise RequiredKeyError(key, section=section)
    confix.RequiredKeyError: configuration class requires 'password' setting key to be specified via configuration file or environment variable


Default validators
------------------

confix provides a bunch of validators by default. This example shows all of
them:

.. code-block:: python

    # main.py
    from confix import register, schema, istrue, isin, isnotin, isemail
    from confix import isip4, isip6, isip46

    @register()
    class config:
        username = schema('john', validator=istrue)
        status = schema('active', validator=isin(['active', inactive]))
        password = schema(None, mandatory=True,
                          validator=isnotin(['12345', 'password']))
        email = schema('user@domain.com', validator=isemail)
        ipv4_addr = schema('127.0.0.1', validator=isip4)
        ipv6_addr = schema('::1', validator=isip6)
        any_addr = schema('::1', validator=isip46)


Chained validators
------------------

You can define more than one validator per-schema:

.. code-block:: python

    # main.py
    from confix import register, schema, isemail, isnotin,

    @register()
    class config:
        email = schema('user@domain.com',
                       validator=[isemail, isnoin(['info@domain.com']))


Custom validators
-----------------

A validator is a function which receives the overidden value as first argument
and fails if it does not return ``True``. ``confix.ValidationError`` exception
can be raised instead of returning ``False`` to provide a detailed error
message. Example of a custom validator:

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
you want to control everything from a single configuration file having
different sections.
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

configuration file:

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
  environment variable via cmdline ``username`` setting key of both config classes
  would have been overwritten.
- we may also have defined a third "root" config class, with no section.

Notes about @register
---------------------

Classes registered via :func:`confix.register` decorator have a bunch of
peculiarities:

- attributes starting with an underscore will be ignored.
- attributes can be accessed both as normal attributes (``config.foo``) and
  as a ``dict`` (``config['foo']``).
- ``dict()`` can be used against the registered class in order to get the
  whole configuration.
- the config class can have class methods.

.. code-block:: python

    >>> import confix
    >>>
    >>> @confix.register()
    >>> class config:
    ...     foo = 1
    ...     bar = 2
    ...     _apple = 3
    ...
    >>> config.foo
    1
    >>> config['foo']
    1
    >>> dict(config)
    {'foo': 1, 'bar': 2}
    >>>

INI files
---------

INI files are supported but since they are based on "sections" also your
configuration class(es) must have sections.

.. code-block:: python

    # main.py
    from confix import register, parse

    @register()
    class config:
        foo = 2

    parse()

.. code-block:: text

    $ python main.py
    Traceback (most recent call last):
      File "main.py", line 8, in <module>
        parse('config.ini')
      File "/home/giampaolo/svn/confix/confix.py", line 693, in parse
        type_check=type_check)
      File "/home/giampaolo/svn/confix/confix.py", line 440, in __init__
        self.new_conf = self.get_conf_from_file()
      File "/home/giampaolo/svn/confix/confix.py", line 483, in get_conf_from_file
        raise Error("can't parse ini files if a sectionless "
    confix.Error: can't parse ini files if a sectionless configuration class has been registered

This means that if you have an INI file you must define
`multiple configuration classes <#multiple-configuration-classes>`_,
each one with a different section name.


Supporting other file formats
-----------------------------

By default confix supports YAML, JSON, INI and TOML configuration formats.
If you want to add a new format you can write a parser for that specific format
as a function, have it return a dict and pass it to :func`confix.parse()`.
Example:


.. code-block:: python

    # main.py
    from confix import register, parse

    @register()
    class config:
        foo = 1

    def parse_new_format():
        return {}

    parse('config.ext', file_parser=parse_new_format)
