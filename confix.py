#!/usr/bin/env python

"""
A language-agnostic configuration parser.
Currently supports YAML, JSON, INI and TOML serialization formats.
"""

import collections
import contextlib
import functools
import inspect
import json
import logging
import multiprocessing
import os
import re
import sys
import threading
import warnings

try:
    import configparser  # py3
except ImportError:
    import ConfigParser as configparser

__all__ = [
    # constants
    "version_info", "__version__",
    # functions
    'register', 'parse', 'parse_with_envvars', 'discard', 'schema',
    'get_parsed_conf',
    # validators
    'isemail', 'isin', 'isnotin', 'istrue', 'isurl', 'isip46', 'isip4',
    'isip6',
    # exceptions
    'Error', 'ValidationError', 'AlreadyParsedError', 'NotParsedError',
    'RequiredSettingKeyError', 'TypesMismatchError', 'AlreadyRegisteredError',
    'UnrecognizedSettingKeyError',
]
__version__ = '0.2.2'
__author__ = 'Giampaolo Rodola'
__license__ = 'MIT'
version_info = tuple([int(num) for num in __version__.split('.')])

_PY3 = sys.version_info >= (3, )
# TODO: these are currently treated as case-insensitive; instead we should
# do "True", "TRUE" etc and ignore "TrUe".
_STR_BOOL_TRUE = set(("1", "yes", "true", "on"))
_STR_BOOL_FALSE = set(("0", "no", "false", "off"))
_EMAIL_RE = re.compile("^.+@.+\..+$")
# http://stackoverflow.com/a/7995979/376587
_URL_RE = re.compile(
    r'^https?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
    r'localhost|'  # localhost
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IPv4
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)
_DEFAULT = object()
_threading_lock = threading.Lock()
_multiprocessing_lock = multiprocessing.Lock()
_conf_map = {}
_parsed = False
logger = logging.getLogger(__name__)


if _PY3:
    basestring = str
    unicode = str


# =============================================================================
# exceptions
# =============================================================================


class Error(Exception):
    """Base exception class from which derive all others."""

    def __repr__(self):
        return self.__str__()


class ValidationError(Error):
    """Raised when validation through schema(validator=callable)
    doesn't pass (callable return False).

    This can be used within your validator in order to throw custom
    error messages.
    """

    def __init__(self, msg=None):
        self.msg = msg
        # these are set later in parse()
        self.section = None
        self.key = None
        self.value = None

    def __str__(self):
        key = "'%s.%s'" % (self.section, self.key) if self.section else \
            repr(self.key)
        msg = "%s setting key with value %r didn't pass validation" % (
            key, self.value)
        if self.msg:
            msg += "; %s" % self.msg
        return msg


class AlreadyParsedError(Error):
    """Raised when parse() or parse_with_envvars() is called twice."""

    def __str__(self):
        return 'configuration was already parsed once; you may want to use ' \
               'discard() and parse() again'


class AlreadyRegisteredError(Error):
    """Raised by @register when registering the same section twice."""

    def __init__(self, section):
        self.section = section

    def __str__(self):
        return "a configuration class was already registered for " \
               "section %r" % self.section


class NotParsedError(Error):
    """Raised when get_parsed_conf() is called but parse() has not been
    called yet.
    """

    def __str__(self):
        return 'configuration is not parsed yet; use parse() first'


# --- exceptions raised on parse()


class UnrecognizedSettingKeyError(Error):
    """Raised on parse if the configuration file defines a setting key
    which is not defined by the default configuration class.
    """

    def __init__(self, section, key, new_value):
        self.section = section
        self.key = key
        self.new_value = new_value

    def __str__(self):
        if not _has_multi_conf_classes() and _conf_map:
            klass = _conf_map[None]
            txt = "config class %s.%s" % (klass.__module__, klass.__name__)
        else:
            txt = "any of the config classes"
        key = "%s.%s" % (self.section, self.key) if self.section else self.key
        return ("config file provides setting key %r with value %r but "
                "setting key %r is not defined in %s" % (
                    key, self.new_value, key, txt))


class RequiredSettingKeyError(Error):
    """Raised when the config file doesn't specify a setting key which
    was required via schema(required=True).
    """

    def __init__(self, section, key):
        self.section = section
        self.key = key

    def __str__(self):
        key = "%s.%s" % (self.section, self.key) if self.section else self.key
        return "configuration class requires %r setting key to be specified " \
               "via config file or environment variable" % (key)


class TypesMismatchError(Error):
    """Raised when config file overrides a setting key having a type
    which is different than the original one defined in the
    configuration class.
    """

    def __init__(self, section, key, default_value, new_value):
        self.section = section
        self.key = key
        self.default_value = default_value
        self.new_value = new_value

    def __str__(self):
        key = "%s.%s" % (self.section, self.key) if self.section else self.key
        return "type mismatch for setting key %r (default_value=%r, %s) got " \
               "%r (%s)" % (key, self.default_value, type(self.default_value),
                            self.new_value, type(self.new_value))


# =============================================================================
# internal utils
# =============================================================================


def _log(s):
    logger.debug(s)


def _has_multi_conf_classes():
    """Return True if more than one config class has been register()ed."""
    return len(_conf_map) > 1


def _has_sectionless_conf(cmap=None):
    if cmap is None:
        cmap = _conf_map
    return None in cmap


@contextlib.contextmanager
def _lock_ctx():
    with _threading_lock:
        with _multiprocessing_lock:
            yield


# =============================================================================
# validators
# =============================================================================


def istrue(value):
    """Assert value evaluates to True."""
    if not bool(value):
        raise ValidationError("bool(%r) evaluates to False" % value)
    return True


def isin(seq):
    """Assert value is in a sequence."""
    def wrapper(seq, value):
        if value not in seq:
            raise ValidationError(
                "expected a value amongst %r, got %r" % (seq, value))
        return True

    if not isinstance(seq, collections.Iterable):
        raise TypeError("%r is not iterable" % (seq))
    if not seq:
        raise ValueError("%r sequence can't be empty" % (seq))
    return functools.partial(wrapper, seq)


def isnotin(seq):
    """Assert value is not in a sequence."""
    def wrapper(seq, value):
        if value in seq:
            raise ValidationError(
                "expected a value not in %r sequence, got %r" % (seq, value))
        return True

    if not isinstance(seq, collections.Iterable):
        raise TypeError("%r is not iterable".format(seq))
    if not seq:
        raise ValueError("%r sequence can't be empty".format(seq))
    return functools.partial(wrapper, seq)


def isemail(value):
    """Assert value is a valid email."""
    if not isinstance(value, basestring):
        raise ValidationError("expected a string, got %r" % value)
    if re.match(_EMAIL_RE, value) is None:
        raise ValidationError("not a valid email")
    return True


def isurl(value):
    """Assert value is a valid url. This includes urls starting with
    "http" and "https", IPv4 urls (e.g. "http://127.0.0.1") and
    optional port (e.g. "http://localhost:8080").
    """
    if not isinstance(value, basestring):
        raise ValidationError("expected a string, got %r" % value)
    if re.match(_URL_RE, value) is None:
        raise ValidationError("not a valid URL")
    return True


def isip46(value):
    """Assert value is a valid IPv4 or IPv6 address.
    On Python < 3.3 requires ipaddress module to be installed.
    """
    import ipaddress  # requires "pip install ipaddress" on python < 3.3
    if not isinstance(value, basestring):
        raise ValidationError("expected a string, got %r" % value)
    if not _PY3 and not isinstance(value, unicode):
        value = unicode(value)
    try:
        if "/" in value:
            raise ValueError
        ipaddress.ip_address(value)
    except ValueError:
        raise ValidationError("not a valid IP address")
    return True


def isip4(value):
    """Assert value is a valid IPv4 address."""
    if not isinstance(value, basestring):
        raise ValidationError("expected a string, got %r" % value)
    octs = value.split('.')
    try:
        assert len(octs) == 4
        for x in octs:
            x = int(x)
            assert x >= 0 and x <= 255
    except (AssertionError, ValueError):
        raise ValidationError("not a valid IPv4 address")
    return True


def isip6(value):
    """Assert value is a valid IPv6 address.
    On Python < 3.3 requires ipaddress module to be installed.
    """
    import ipaddress  # requires "pip install ipaddress" on python < 3.3
    if not isinstance(value, basestring):
        raise ValidationError("expected a string, got %r" % value)
    if not _PY3 and not isinstance(value, unicode):
        value = unicode(value)
    try:
        ipaddress.IPv6Address(value)
    except ValueError:
        raise ValidationError("not a valid IPv6 address")
    return True


# =============================================================================
# parsers
# =============================================================================


def parse_yaml(file):
    import yaml  # requires pip install pyyaml
    return yaml.load(file)


def parse_toml(file):
    import toml  # requires pip install toml
    return toml.loads(file.read())


def parse_json(file):
    content = file.read()
    if not content.strip():
        # empty JSON file; do not explode in order to be consistent with
        # other formats (for now at least...)
        return {}
    return json.loads(content)


def parse_ini(file):
    config = configparser.ConfigParser()
    config.read(file.name)
    ret = {}
    for section, values in config._sections.items():
        ret[section] = {}
        for key, value in values.items():
            ret[section][key] = value
        ret[section].pop('__name__', None)
    return ret


# =============================================================================
# rest of public API
# =============================================================================


class schema(collections.namedtuple('field',
             ['default', 'required', 'validator'])):

    def __new__(cls, default=_DEFAULT, required=False, validator=None):
        if not required and default is _DEFAULT:
            raise ValueError("specify a default value or set required=True")
        if validator is not None:
            if not isinstance(validator, collections.Iterable):
                if not callable(validator):
                    raise TypeError("%r is not callable" % validator)
            else:
                for v in validator:
                    if not callable(v):
                        raise TypeError("%r is not callable" % v)
        return super(schema, cls).__new__(cls, default, required, validator)


def register(section=None):
    """A decorator which registers a configuration class which will
    be parsed later.
    If `section` is `None` it is assumed that the configuration file
    will not be split in sub-sections otherwise *section* is the name
    of a specific section which will be referenced by the config file.
    All class attributes starting with an underscore will be ignored,
    same for methods, classmethods or any other non-callable type.
    A class decoratored with this method becomes dict()-able.
    """
    class meta_wrapper(type):

        def __iter__(self):
            # this will make the class dict()able
            for k, v in inspect.getmembers(self):
                if not k.startswith('_') and not inspect.isroutine(v):
                    yield (k, v)

        def __getitem__(self, key):
            return getattr(self, key)

        def __delitem__(self, key):
            delattr(self, key)

        def __contains__(self, key):
            return hasattr(self, key)

        def __len__(self):
            return len(dict(self))

    def add_metaclass(klass):
        name = klass.__name__
        bases = klass.__bases__
        # is this really necessary?
        skip = set(('__dict__', '__weakref__'))
        dct = dict((k, v) for k, v in vars(klass).items() if k not in skip)
        new_class = meta_wrapper(name, bases, dct)
        return new_class

    def wrapper(klass):
        if not inspect.isclass(klass):
            raise TypeError("register decorator is supposed to be used "
                            "against a class (got %r)" % klass)
        _log("registering %s.%s" % (klass.__module__, klass.__name__))
        with _lock_ctx():
            new_class = add_metaclass(klass)
            _conf_map[section] = new_class
        return new_class

    with _lock_ctx():
        if section in _conf_map:
            raise AlreadyRegisteredError(section)

        if _parsed:
            msg = "configuration class defined after parse(); global " \
                  "configuration will not reflect it and it will remain " \
                  "unparsed"
            warnings.warn(msg, UserWarning)
            return lambda klass: add_metaclass(klass)

        if _has_sectionless_conf():
            # There's a root section. Verify the new key does not
            # override any of the keys in the root section.
            root_conf_class = _conf_map.get(None)
            if section in root_conf_class:
                raise Error(
                    "attempting to register section %r when previously "
                    "registered root class %r already defines a section with "
                    "the same name" % (section, root_conf_class))

    if section is not None and not isinstance(section, basestring):
        raise TypeError("invalid section; expected either string or None, "
                        "got %r" % section)
    if isinstance(section, basestring):
        if " " in section or not section.strip():
            raise ValueError("invalid section name %r" % section)
    return wrapper


def get_parsed_conf():
    """Return the whole parsed configuration as a dict.
    If parse() wasn't called yet it will raise NotParsedError.
    """
    with _lock_ctx():
        if not _parsed:
            raise NotParsedError
        conf_map = _conf_map.copy()
    ret = {}
    # root section
    if _has_sectionless_conf(conf_map):
        conf_class = conf_map.pop(None)
        ret = dict(conf_class)
    # other sections
    for section, conf_class in conf_map.items():
        ret[section] = dict(conf_class)
    return ret


class _Parser:

    def __init__(self, conf_file=None, file_parser=None, type_check=True,
                 parse_envvars=False, envvar_case_sensitive=False):
        """Do all the work."""
        global _parsed
        if _parsed:
            raise AlreadyParsedError
        self.conf_file = conf_file
        self.file_parser = file_parser
        self.type_check = type_check
        self.envvar_case_sensitive = envvar_case_sensitive
        self.file_ext = None

        self.new_conf = self.get_conf_from_file()
        if parse_envvars:
            self.update_conf_from_envvars()
        self.process_conf(self.new_conf)
        _parsed = True

    def get_conf_from_file(self):
        """Parse config file (if any) and returns a dict representation
        of it (can also be an empty dict).
        """
        # no conf file
        if self.conf_file is None:
            _log("conf file not specified")
            if self.file_parser is not None:
                raise ValueError(
                    "can't specify 'file_parser' option and no 'conf_file'")
            else:
                return {}

        # parse conf file
        if isinstance(self.conf_file, basestring):
            file = open(self.conf_file, 'r')
            _log("using conf file %s" % (self.conf_file))
        else:
            file = self.conf_file
            _log("using conf file-like object %s" % (self.conf_file))
        with file:
            pmap = {'.yaml': parse_yaml,
                    '.yml': parse_yaml,
                    '.toml': parse_toml,
                    '.json': parse_json,
                    '.ini': parse_ini}
            if self.file_parser is None:
                if not hasattr(file, 'name'):
                    raise Error("can't determine file format from a file "
                                "object with no 'name' attribute")
                try:
                    self.file_ext = os.path.splitext(file.name)[1]
                    parser = pmap[self.file_ext]
                except KeyError:
                    raise ValueError("don't know how to parse %r (extension "
                                     "not supported)" % file.name)
                if self.file_ext == '.ini' and _has_sectionless_conf():
                    raise Error("can't parse ini files if a sectionless "
                                "configuration class has been registered")
            else:
                parser = self.file_parser
            return parser(file) or {}

    def update_conf_from_envvars(self):
        """Iterate over all process env vars and return a dict() of
        env vars whose name match they setting keys defined by conf
        class.
        """
        conf_map = _conf_map.copy()
        env = os.environ.copy()
        env_names = set([x for x in env.keys() if x.isupper()])
        for section, conf_class in conf_map.items():
            for key_name in dict(conf_class).keys():
                check_name = (
                    key_name.upper() if not self.envvar_case_sensitive
                    else key_name)
                if check_name in env_names:
                    default_value = getattr(conf_class, key_name)
                    raw_value = env[key_name.upper()]
                    new_value = self.cast_value(
                        section, key_name, default_value, raw_value)
                    if section is None:
                        self.new_conf[key_name] = new_value
                    else:
                        if section not in self.new_conf:
                            self.new_conf[section] = {}
                        self.new_conf[section][key_name] = new_value

    def cast_value(self, section, key, default_value, new_value):
        """Cast a value depending on default value type."""
        if isinstance(default_value, schema):
            default_value = default_value.default
        if isinstance(default_value, bool):
            if new_value.lower() in _STR_BOOL_TRUE:
                new_value = True
            elif new_value.lower() in _STR_BOOL_FALSE:
                new_value = False
            else:
                if self.type_check:
                    raise TypesMismatchError(
                        section, key, default_value, new_value)
        elif isinstance(default_value, int):
            try:
                new_value = int(new_value)
            except ValueError:
                if self.type_check:
                    raise TypesMismatchError(
                        section, key, default_value, new_value)
        elif isinstance(default_value, float):
            try:
                new_value = float(new_value)
            except ValueError:
                if self.type_check:
                    raise TypesMismatchError(
                        section, key, default_value, new_value)
        else:
            # leave the new value unmodified (str)
            pass
        return new_value

    def process_conf(self, new_conf):
        conf_map = _conf_map.copy()
        if not conf_map:
            raise Error("no registered conf classes were found")
        # iterate over file / envvar conf
        for key, new_value in new_conf.items():
            # this should never happen
            assert key is not None, key
            if key in conf_map:
                # We're dealing with a section.
                # Possibly we may have multiple regeister()ed conf classes.
                # "new_value" in this case is actually a dict of sub-section
                # items.
                section = key
                conf_class = conf_map[section]
                # TODO: turn this into a proper error
                assert isinstance(new_value, dict), new_value
                # assert new_value, new_value
                for k, nv in new_value.items():
                    self.process_pair(section, k, nv, conf_class)
            else:
                # We're not dealing with a section.
                section = None
                try:
                    conf_class = conf_map[None]
                except KeyError:
                    raise UnrecognizedSettingKeyError(None, key, new_value)
                self.process_pair(section, key, new_value, conf_class)

        self.run_last_schemas()

    def process_pair(self, section, key, new_value, conf_class):
        """Given a setting key / value pair extracted either from the
        config file or env vars process it (validate it) and override
        the config class original key value.
        """
        try:
            # The default value defined in the conf class.
            default_value = getattr(conf_class, key)
        except AttributeError:
            # Conf file defines a key which does not exist in the
            # conf class.
            raise UnrecognizedSettingKeyError(section, key, new_value)

        # Cast values for ini files (which only support string type).
        if self.file_ext == '.ini':
            new_value = self.cast_value(section, key, default_value, new_value)

        # Look for type mismatch.
        is_schema = isinstance(default_value, schema)
        if not is_schema:
            self.check_type(section, key, default_value, new_value)

        # Run validators.
        if is_schema:
            schema_ = default_value
            if schema_.validator is not None:
                self.run_validators(schema_, section, key, new_value)

        # Finally replace key value.
        sec_key = key if section is None else "%s.%s" % (section, key)
        _log("overriding setting key %r (value=%r) to new value %r".format(
            sec_key, default_value, new_value))
        setattr(conf_class, key, new_value)

    def check_type(self, section, key, default_value, new_value):
        """Raise TypesMismatchError if config file or env var wants to
        override a setting key with a type which is different than the
        original one defined in the config class.
        """
        doit = (self.type_check and
                default_value is not None and
                new_value is not None)
        if doit and type(new_value) != type(default_value):
            if (not _PY3 and
                    isinstance(new_value, basestring) and
                    isinstance(default_value, basestring)):
                # On Python 2 we don't want to make a distinction
                # between str and unicode.
                pass
            else:
                raise TypesMismatchError(
                    section, key, default_value, new_value)

    @staticmethod
    def run_validators(schema_, section, key, new_value):
        """Run schema validators and raise ValidationError on failure."""
        validators = schema_.validator
        if not isinstance(validators, collections.Iterable):
            validators = [validators]
        for validator in validators:
            exc = None
            sec_key = key if section is None else "%s.%s" % (section, key)
            _log("running validator %r for key %r with value "
                 "%r".format(validator, sec_key, new_value))
            try:
                ok = validator(new_value)
            except ValidationError as err:
                exc = ValidationError(err.msg)
            else:
                if not ok:
                    exc = ValidationError()
            if exc is not None:
                exc.section = section
                exc.key = key
                exc.value = new_value
                raise exc

    @staticmethod
    def run_last_schemas():
        """Iterate over configuration classes in order to collect all
        schemas which were not overwritten by the config file.
        """
        conf_map = _conf_map.copy()
        for section, conf_class in conf_map.items():
            for key, value in conf_class.__dict__.items():
                if isinstance(value, schema):
                    schema_ = value
                    if schema_.required:
                        raise RequiredSettingKeyError(section, key)
                    if schema_.validator is not None:
                        _Parser.run_validators(schema_, section, key, value)
                    setattr(conf_class, key, value.default)


def parse(conf_file=None, file_parser=None, type_check=True):
    """Parse configuration class(es) replacing values if a
    configuration file is provided.

    Params:

    - (str|file) conf_file: a path to a configuration file or an
      existing file-like object or None.
      If `None` configuration class will be parsed anyway in order
      to validate `schema`s.

    - (callable) file_parser: the function parsing the configuration
      file and converting it to a dict.  If `None` a default parser
      will be picked up depending on the file extension.
      You may want to override this either to support new file
      extensions or types.

    - (bool) type_check: when `True` raise `TypesMismatchError` in
      case an option specified in the configuration file has a different
      type than the one defined in the configuration class.
    """
    with _lock_ctx():
        _Parser(conf_file=conf_file, file_parser=file_parser,
                type_check=type_check)


def parse_with_envvars(conf_file=None, file_parser=None, type_check=True,
                       case_sensitive=False):
    """Same as parse() but also takes environment variables into account.
    It must be noted that env vars take precedence over the config file
    (if specified).
    Only upper cased environment variables are taken into account.
    By default (case_sensitive=False) env var "FOO" will override a
    setting key with the same name in a non case sensitive fashion
    ('foo', 'Foo', 'FOO', etc.).
    Also "sections" are not supported so if multiple config classes
    define a setting key "foo" all of them will be overwritten.
    If `case_sensitive` is True then it is supposed that the config
    class(es) define all upper cased setting keys.
    """
    with _lock_ctx():
        _Parser(conf_file=conf_file,
                file_parser=file_parser,
                type_check=type_check,
                parse_envvars=True,
                envvar_case_sensitive=case_sensitive)


def discard():
    """Discard previous configuration (if any)."""
    global _parsed
    with _lock_ctx():
        _conf_map.clear()
        _parsed = False


if not _PY3:
    del num
