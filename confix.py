#!/usr/bin/env python

"""
A language-agnostic configuration parser.
Currently supports YAML, JSON, INI and TOML serialization formats.
"""

# TODO / IDEAS / OPEN QUESTIONS:
# - have @register modify the conf class in order to provide / attach:
#   - a nice __repr__
#   - a nice __dir__
# - should parse() return get_parsed_conf()?
# - when using multiple conf classes raise exception if a sub section
#   overrides a root key
# - add 'transformer' callable to schema
# - schema: figure out what do in case no default value is specified

import collections
import functools
import inspect
import json
import logging
import os
import re
import sys

try:
    import configparser  # py3
except ImportError:
    import ConfigParser as configparser


__all__ = ['register', 'parse', 'discard', 'schema', 'ValidationError']
__version__ = '0.2.0'
__author__ = 'Giampaolo Rodola'
__license__ = 'MIT'

_PY3 = sys.version_info >= (3, )
_BOOL_TRUE = set(("1", "yes", "true", "on"))
_BOOL_FALSE = set(("0", "no", "false", "off"))
_EMAIL_RE = re.compile("^.+@.+\..+$")

if _PY3:
    basestring = str


logger = logging.getLogger(__name__)


# =============================================================================
# exceptions (public)
# =============================================================================


class Error(Exception):
    """Base exception class from which derive all others."""

    def __repr__(self):
        return self.__str__()


class ValidationError(Error):
    """Raised when validation through schema(validator=callable)
    doesn't pass (callable return False).

    This can be used within your validator in order to throw custom
    error messages (...and it's the only exception class which is
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
    """Called when parse() or parse_with_envvars() is called twice."""

    def __str__(self):
        return 'configuration was already parsed once; you may want to use ' \
               'discard() and parse() again'


class NotParsedError(Error):
    """Called when get_parsed_conf() is called but parse() has not been
    called yet.
    """

    def __str__(self):
        return 'configuration is not parsed yet; use parse() first'


# =============================================================================
# exceptions (internal)
# =============================================================================


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
    """Return True if more than config class has been register()ed."""
    return len(_conf_map) > 1


# =============================================================================
# validators
# =============================================================================


def istrue(value):
    """Assert value evaluates to True."""
    try:
        assert bool(value)
    except AssertionError:
        raise ValidationError("bool(%r) evaluates to False" % value)
    else:
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
    import yaml
    return yaml.load(file.read())


def parse_toml(file):
    import toml
    return toml.loads(file.read())


def parse_json(file):
    content = file.read()
    if not content.strip():
        # empty JSON file; do not explode in order to be consistent with
        # other formats (for now at least...)
        return {}
    return json.loads(content)


def parse_envvar(name, value, default_value):
    if isinstance(default_value, schema):
        default_value = default_value.default
    if isinstance(default_value, bool):
        if value.lower() in _BOOL_TRUE:
            value = True
        elif value.lower() in _BOOL_FALSE:
            value = False
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
    _log("envvar=%s, value=%r, default_value=%r, "
         "casted_to=%r" % (name, value, default_value, value))
    return value


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


# =============================================================================
# rest of public API
# =============================================================================


_conf_map = {}
_parsed = False
_DEFAULT = object()


class schema(collections.namedtuple('field',
             ['default', 'required', 'validator'])):

    def __new__(cls, default=_DEFAULT, required=False, validator=None):
        if not required and default is _DEFAULT:
            raise TypeError("specify a default value or set required=True")
        if validator is not None:
            if not isinstance(validator, collections.Iterable):
                if not callable(validator):
                    raise ValueError("%r is not callable" % validator)
            else:
                for v in validator:
                    if not callable(v):
                        raise ValueError("%r is not callable" % v)
        return super(schema, cls).__new__(cls, default, required, validator)


def register(section=None):
    """Register a configuration class which will be parsed later."""
    def wrapper(klass):
        if not inspect.isclass(klass):
            raise TypeError("register decorator is supposed to be used "
                            "against a class (got %r)" % klass)
        _conf_map[section] = klass
        _log("registering %s.%s" % (klass.__module__, klass.__name__))
        return klass

    if section in _conf_map:
        raise ValueError("a conf class was already registered for "
                         "section %r" % section)
    return wrapper


def get_parsed_conf():
    """Return the whole parsed configuration as a dict.
    If parse() wasn't called yet it will raise NotParsedError.
    """
    def conf_class_to_dict(conf_class):
        ret = {}
        for k, v in inspect.getmembers(conf_class):
            if not k.startswith('_') and not inspect.isroutine(v):
                ret[k] = v
        return ret

    if not _parsed:
        raise NotParsedError
    ret = {}
    cmap = _conf_map.copy()
    # root section
    if None in cmap:
        conf_class = cmap.pop(None)
        ret = conf_class_to_dict(conf_class)
    # other sections
    for section, conf_class in cmap.items():
        ret[section] = conf_class_to_dict(conf_class)
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
                    raise Error("can't determine format from a file "
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
        conf_class = _conf_map[None]
        conf_class_names = set(conf_class.__dict__.keys())
        if not self.envvar_case_sensitive:
            conf_class_names = set([x.lower() for x in conf_class_names])

        conf = {}
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
        if not _conf_map:
            raise Error("no registered conf classes were found")

        # iterate over file / envvar conf
        for key, new_value in conf.items():
            # this should never happen
            assert key is not None, key
            if key in _conf_map:
                # We're dealing with a section.
                # Possibly we may have multiple regeister()ed conf classes.
                # "new_value" in this case is actually a dict of sub-section
                # items.
                conf_class = _conf_map[key]
                assert isinstance(new_value, dict), new_value
                assert new_value, new_value
                for k, nv in new_value.items():
                    self.process_pair(k, nv, conf_class, section=key)
            else:
                # We're not dealing with a section.
                try:
                    conf_class = _conf_map[None]
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

        is_schema = isinstance(default_value, schema)
        # TODO: perhpas "not is_schema" is not necessary
        check_type = (
            self.type_check and
            not is_schema and
            default_value is not None and
            new_value is not None
        )
        if check_type and type(new_value) != type(default_value):
            # Config file overrides a key with a type which is
            # different than the original one defined in the
            # conf class.
            if (not _PY3 and
                    isinstance(new_value, basestring) and
                    isinstance(default_value, basestring)):
                # On Python 2 we don't want to make a distinction
                # between str and unicode.
                pass
            else:
                raise TypesMismatchError(key, default_value, new_value,
                                         section=section)

        if is_schema and default_value.validator is not None:
            schema_ = default_value
            self.run_validators(schema_, section, key, new_value)

        _log("overring key %r (value=%r) to new value %r".format(
            key, getattr(conf_class, key), new_value))
        setattr(conf_class, key, new_value)

    @staticmethod
    def run_validators(schema_, section, key, new_value):
        validators = schema_.validator
        if not isinstance(validators, collections.Iterable):
            validators = [validators]
        for validator in validators:
            exc = None
            _log("running validator %r for key %r with value "
                 "%r".format(validator, key, new_value))
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
        for section, conf_class in _conf_map.items():
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
    _Parser(conf_file=conf_file,
            file_parser=file_parser,
            type_check=type_check,
            parse_envvars=True,
            envvar_case_sensitive=case_sensitive,
            envvar_parser=envvar_parser)


def discard():
    """Discard previous configuration (if any)."""
    global _parsed
    _conf_map.clear()
    _parsed = False
