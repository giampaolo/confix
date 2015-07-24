#!/usr/bin/env python

"""
A language-agnostic configuration parser.
Currently supports YAML, JSON, INI and TOML serialization formats.
"""

# @register()
# -----------
# TODO: provide __repr__?
# TODO: provide __dir__?
# TODO: should we raise exception if config class has key starting with "_"
#       instead of skipping it?
# TODO: provide some kind of isinstance() check for @register()ed classes?
# TODO: should we check class is not instantiated?
# TODO: should we avoid instantiation in metaclass_wrapper
#       (exception from __init__)?

# parse()
# -------
# TODO: should we rollback() and reset _conf_map on validation error?
# TODO: should parse() return get_parsed_conf()?
# TODO: add _after_parse callback? (it's gonna be a class method)
# TODO: add 'transformer' callable to schema?
#       should it be executed before or after validate?
#       should it be executed for the default value as well (probably not)?

# parse_with_envvars()
# --------------------
# TODO: not happy with `case_sensitive` arg

# schema()
# --------
# TODO: schema: figure out what do in case no default value is specified
# TODO: move running of validation into schema (validate() method)


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
    'isemail', 'isin', 'isnotin', 'istrue',
    # exceptions
    'Error', 'ValidationError', 'AlreadyParsedError', 'NotParsedError',
    'RequiredKeyError', 'TypesMismatchError', 'UnrecognizedKeyError',
    'AlreadyRegisteredError',
]
__version__ = '0.2.0'
__author__ = 'Giampaolo Rodola'
__license__ = 'MIT'
version_info = tuple([int(num) for num in __version__.split('.')])

_PY3 = sys.version_info >= (3, )
_BOOL_TRUE = set(("1", "yes", "true", "on"))
_BOOL_FALSE = set(("0", "no", "false", "off"))
_EMAIL_RE = re.compile("^.+@.+\..+$")
_DEFAULT = object()
_threading_lock = threading.Lock()
_multiprocessing_lock = multiprocessing.Lock()
_conf_map = {}
_parsed = False
logger = logging.getLogger(__name__)


if _PY3:
    basestring = str


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
        msg = "%s key with value %r didn't pass validation" % (key, self.value)
        if self.msg:
            msg += "; %s" % self.msg
        return msg


class AlreadyParsedError(Error):
    """Raised when parse() or parse_with_envvars() is called twice."""

    def __str__(self):
        return 'configuration was already parsed once; you may want to use ' \
               'discard() and parse() again'


class AlreadyRegisteredError(Error):
    """Raised by @register when registering a class twice."""

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


class UnrecognizedKeyError(Error):
    """Raised when the configuration class does not define a key but
    that is defined in the config file.
    """

    def __init__(self, key, value, section=None, msg=None):
        self.key = key
        self.value = value
        self.section = section
        self.msg = msg

    def __str__(self):
        plural = "es" if _has_multi_conf_classes() else ""
        key = "%s.%s" % (self.section, self.key) if self.section else self.key
        return self.msg or \
            "config file provides key %r with value %r but key %r is not " \
            "defined in the config class%s" % (
                key, self.value, key, plural)


class RequiredKeyError(Error):
    """Raised when the config file didn't specify a required key
    (enforced by a schema()).
    """

    def __init__(self, key, section=None, msg=None):
        self.key = key
        self.msg = msg
        self.section = section

    def __str__(self):
        key = "%s.%s" % (self.section, self.key) if self.section else self.key
        return self.msg or \
            "configuration class requires %r key to be specified via config " \
            "file or env var" % (key)


class TypesMismatchError(Error):
    """Raised when config file overrides a key having a type different
    than the original one defined in the configuration class.
    """

    def __init__(self, key, default_value, new_value, section=None, msg=None):
        self.key = key
        self.default_value = default_value
        self.new_value = new_value
        self.section = section
        self.msg = msg

    def __str__(self):
        key = "%s.%s" % (self.section, self.key) if self.section else self.key
        return self.msg or \
            "type mismatch for key %r (default_value=%r, %s) got %r " \
            "(%s)" % (
                key, self.default_value, type(self.default_value),
                self.new_value, type(self.new_value))


# =============================================================================
# internal utils
# =============================================================================


def _log(s):
    logger.debug(s)


def _has_multi_conf_classes():
    """Return True if more than one config class has been register()ed."""
    with _lock_ctx():
        return len(_conf_map) > 1


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


# =============================================================================
# parsers
# =============================================================================


def parse_yaml(file):
    import yaml  # requires pip install pyyaml
    return yaml.load(file.read())


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
            value_stripped = value.strip()
            if value.isdigit():
                value = int(value)
            elif value_stripped in _BOOL_TRUE:
                value = True
            elif value_stripped in _BOOL_FALSE:
                value = False
            else:
                # guard against float('inf') which returns 'infinite'
                if value_stripped != 'inf':
                    try:
                        value = float(value)
                    except ValueError:
                        pass
            ret[section][key] = value
        ret[section].pop('__name__', None)
    return ret


def parse_envvar(name, value, default_value):
    if isinstance(default_value, schema):
        default_value = default_value.default
    if isinstance(default_value, bool):
        if value.lower() in _BOOL_TRUE:
            value = True
        elif value.lower() in _BOOL_FALSE:
            value = False
        else:
            raise TypesMismatchError(name, default_value, value)
    elif isinstance(default_value, int):
        try:
            value = int(value)
        except ValueError:
            raise TypesMismatchError(name, default_value, value)
    elif isinstance(default_value, float):
        try:
            value = float(value)
        except ValueError:
            raise TypesMismatchError(name, default_value, value)
    else:
        # leave the value unmodified (str)
        pass
    _log("envvar=%s, value=%r, default_value=%r, "
         "casted_to=%r" % (name, value, default_value, value))
    return value


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

        # XXX: it seems this is not necessary (why?)
        # def __setitem__(self, key, value):
        #     setattr(self, key, value)

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
            klass = add_metaclass(klass)
            _conf_map[section] = klass
        return klass

    with _lock_ctx():
        if section in _conf_map:
            raise AlreadyRegisteredError(section)

        if _parsed:
            msg = "configuration class defined after parse(); global " \
                  "configuration will not reflect it and it will remain " \
                  "unparsed"
            warnings.warn(msg, UserWarning)
            return lambda klass: add_metaclass(klass)

        if None in _conf_map:
            # There's a root section. Verify the new key does not
            # override any of the keys in the root section.
            root_conf_class = _conf_map.get(None)
            if section in root_conf_class:
                raise Error(
                    "attempting to register section %r when previously "
                    "registered root class %r already defines a key with the "
                    "same name" % (section, root_conf_class))

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
    if None in conf_map:
        conf_class = conf_map.pop(None)
        ret = dict(conf_class)
    # other sections
    for section, conf_class in conf_map.items():
        ret[section] = dict(conf_class)
    return ret


class _Parser:

    def __init__(self, conf_file=None, file_parser=None, type_check=True,
                 parse_envvars=False, envvar_case_sensitive=False,
                 envvar_parser=None):
        """Do all the work."""
        global _parsed
        if _parsed:
            raise AlreadyParsedError
        self.conf_file = conf_file
        self.file_parser = file_parser
        self.type_check = type_check
        self.parse_envvars = parse_envvars
        self.envvar_case_sensitive = envvar_case_sensitive
        self.envvar_parser = envvar_parser
        if self.envvar_parser is None:
            self.envvar_parser = parse_envvar
        else:
            if not callable(envvar_parser):
                raise TypeError("envvar_parser is not a callable")

        conf = self.get_conf_from_file()
        if parse_envvars:
            # Note: env vars take precedence over config file.
            conf.update(self.get_conf_from_env())
        self.process_conf(conf)
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
                    '.ini': parse_ini  # TODO
                    }
            if self.file_parser is None:
                if not hasattr(file, 'name'):
                    raise Error("can't determine file format from a file "
                                "object with no 'name' attribute")
                try:
                    ext = os.path.splitext(file.name)[1]
                    parser = pmap[ext]
                except KeyError:
                    raise ValueError("don't know how to parse %r (extension "
                                     "not supported)" % file.name)
            else:
                parser = self.file_parser
            return parser(file) or {}

    def get_conf_from_env(self):
        """Iterate over all process env vars and return a dict() of
        env vars whose name match they keys defined by conf class.
        """
        conf = {}
        conf_map = _conf_map.copy()
        for section, conf_class in conf_map.items():
            conf_class_names = set(conf_class.__dict__.keys())
            if not self.envvar_case_sensitive:
                conf_class_names = set([x.lower() for x in conf_class_names])

            env = os.environ.copy()
            for name, value in env.items():
                if not self.envvar_case_sensitive:
                    name = name.lower()
                if name in conf_class_names:
                    default_value = getattr(conf_class, name)
                    value = self.envvar_parser(name, value, default_value)
                    conf[name] = value
        return conf

    def process_conf(self, conf):
        conf_map = _conf_map.copy()
        if not conf_map:
            raise Error("no registered conf classes were found")
        # iterate over file / envvar conf
        for key, new_value in conf.items():
            # this should never happen
            assert key is not None, key
            if key in conf_map:
                # We're dealing with a section.
                # Possibly we may have multiple regeister()ed conf classes.
                # "new_value" in this case is actually a dict of sub-section
                # items.
                conf_class = conf_map[key]
                assert isinstance(new_value, dict), new_value
                assert new_value, new_value
                for k, nv in new_value.items():
                    self.process_pair(k, nv, conf_class, section=key)
            else:
                # We're not dealing with a section.
                try:
                    conf_class = conf_map[None]
                except KeyError:
                    raise UnrecognizedKeyError(key, new_value, section=None)
                self.process_pair(key, new_value, conf_class,
                                  section=None)

        self.run_last_schemas()

    def process_pair(self, key, new_value, conf_class, section):
        """Given a key / value pair extracted either from the config
        file or env vars process it (validate it) and override the
        config class original key value.
        """
        try:
            # The default value defined in the conf class.
            default_value = getattr(conf_class, key)
        except AttributeError:
            # Conf file defines a key which does not exist in the
            # conf class.
            raise UnrecognizedKeyError(key, new_value, section=section)

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
        _log("overriding key %r (value=%r) to new value %r".format(
            sec_key, default_value, new_value))
        setattr(conf_class, key, new_value)

    def check_type(self, section, key, default_value, new_value):
        """Raise TypesMismatchError if config file or env var wants to
        override a key with a type which is different than the original
        one defined in the conf class.
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
                raise TypesMismatchError(key, default_value, new_value,
                                         section=section)

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
        """Parse the configuration classes in order to collect all schemas
        which were not overwritten by the config file.
        """
        conf_map = _conf_map.copy()
        for section, conf_class in conf_map.items():
            for key, value in conf_class.__dict__.items():
                if isinstance(value, schema):
                    schema_ = value
                    if schema_.required:
                        raise RequiredKeyError(key, section=section)
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
                       case_sensitive=False, envvar_parser=None):
    """Same as parse() but also takes environment variables into account.
    The order of precedence is:

    env-var -> conf-file -> conf-class

    - (bool) case_sensitive: if `False` env var 'FOO' and 'foo' will be
      the treated the same and will override config class' key 'foo'
      (also tread case in a case insensitive manner).

    - (callable) envvar_parser: a callable which is used to convert
      each environment variable value found.
      If a name match is found this function will receive the env var
      name, value and default value (as defined by config class.
      If config class value is an int, float or bool the value will be
      changed in accordance.
    """
    with _lock_ctx():
        _Parser(conf_file=conf_file,
                file_parser=file_parser,
                type_check=type_check,
                parse_envvars=True,
                envvar_case_sensitive=case_sensitive,
                envvar_parser=envvar_parser)


def discard():
    """Discard previous configuration (if any)."""
    global _parsed
    with _lock_ctx():
        _conf_map.clear()
        _parsed = False


if not _PY3:
    del num
