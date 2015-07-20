#!/usr/bin/env python

"""
A language-agnostic configuration parser.
Currently supports YAML, JSON and TOML serialization formats.
"""

# TODO / IDEAS:
# - have @register modify the conf class in order to provide / attach:
#   - a nice __repr__
#   - a nice __dir__
# - re-implement sections
# - re-add ini support (removed because we support section-less conf)

import collections
import inspect
import json
import os
import sys

# try:
#     import configparser  # py3
# except ImportError:
#     import ConfigParser as configparser


__all__ = ['register', 'parse', 'discard', 'schema', 'ValidationError']
__version__ = '0.2.0'
__author__ = 'Giampaolo Rodola'
__license__ = 'MIT'

_PY3 = sys.version_info >= (3, )

if _PY3:
    basestring = str


# --- exceptions (public)

class Error(Exception):
    """Base exception class from which derive all others."""


class ValidationError(Error):
    """Raised when validation through required(validator=callable)
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
        msg = "'%s.%s'" % (self.section, self.key)
        if not self.msg:
            msg += " value is invalid (got %r)" % self.value
        else:
            msg += " %s" % self.msg
        return msg


# --- exceptions (internal)

class InvalidKeyError(Error):
    """Raised when the configuration class does not define a key but
    that is defined in the config file.
    """

    def __init__(self, key, msg=None):
        # TODO: section is not taken into account
        self.key = key
        self.msg = msg

    def __str__(self):
        return self.msg or \
            "configuration class has no value %r but this is defined" \
            " in the config file" % (self.key)


class RequiredKeyError(Error):
    """Raised when the config file didn't specify a required key."""

    def __init__(self, key, msg=None):
        self.key = key
        self.msg = msg

    def __str__(self):
        return self.msg or \
            "configuration class requires %r key to be specified in the " \
            "config file" % (self.key)


class TypesMismatchError(Error):
    """Raised when config file overrides a key having a type different
    than the original one defined in the configuration class.
    """

    def __init__(self, key, default_value, new_value, msg=None):
        self.key = key
        self.default_value = default_value
        self.new_value = new_value
        self.msg = msg

    def __str__(self):
        # TODO: rephrase
        return self.msg or \
            "%s type mismatch expected %r, got %r" % (
                self.key, type(self.default_value), type(self.new_value))


# --- parsers

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


# TODO

# def parse_ini(file):
#     config = configparser.ConfigParser()
#     config.read(file.name)
#     ret = {}
#     bool_true = set(("1", "yes", "true", "on"))
#     bool_false = set(("0", "no", "false", "off"))
#     for section, values in config._sections.items():
#         ret[section] = {}
#         for key, value in values.items():
#             value_stripped = value.strip()
#             if value.isdigit():
#                 value = int(value)
#             elif value_stripped in bool_true:
#                 value = True
#             elif value_stripped in bool_false:
#                 value = False
#             else:
#                 # guard against float('inf') which returns 'infinite'
#                 if value_stripped != 'inf':
#                     try:
#                         value = float(value)
#                     except ValueError:
#                         pass
#             ret[section][key] = value
#         ret[section].pop('__name__', None)
#     return ret


# --- public API

_conf_map = {}
_conf_file = None
_DEFAULT = object()


class schema(collections.namedtuple('field',
             ['default', 'required', 'validator'])):

    def __new__(cls, default=_DEFAULT, required=False, validator=None):
        if not required and default is _DEFAULT:
            raise TypeError("specify a default value or set required=True")
        if validator is not None and not callable(validator):
            raise ValueError("%r is not callable" % validator)
        return super(schema, cls).__new__(cls, default, required, validator)


def register(section=None):
    """Register a configuration class which will be parsed later."""
    def wrapper(klass):
        if not inspect.isclass(klass):
            raise TypeError("register decorator is supposed to be used "
                            "against a class (got %r)" % klass)
        _conf_map[section] = klass
        return klass

    if section is not None:
        # TODO
        raise NotImplementedError("multiple sections not supported yet")
    if section in _conf_map:
        raise ValueError("a conf class was already registered for "
                         "section %r")
    return wrapper


def _process_conf(conf, type_check):
    if not _conf_map:
        raise ValueError("no registered conf classes were found")
    if list(_conf_map.keys()) != [None]:
        raise NotImplementedError("multiple sections not supported yet")

    # TODO: support section
    conf_class_inst = _conf_map[None]

    # iterate over file
    for key, new_value in conf.items():
        try:
            # the default value defined in the conf class
            default_value = getattr(conf_class_inst, key)
        except AttributeError:
            # file defines a key which does not exist in the
            # conf class
            raise InvalidKeyError(key)

        is_schema = isinstance(default_value, schema)
        # TODO: perhpas "not is_schema" is not necessary
        check_type = (
            type_check and
            not is_schema and
            default_value is not None and
            new_value is not None
        )
        if check_type and type(new_value) != type(default_value):
            # config file overrides a key with a type which is
            # different than the original one defined in the
            # conf class
            raise TypesMismatchError(key, default_value, new_value)

        if is_schema and default_value.validator is not None:
            exc = None
            try:
                ok = default_value.validator(new_value)
            except ValidationError as err:
                exc = ValidationError(err.msg)
            else:
                if not ok:
                    exc = ValidationError()
            if exc is not None:
                # exc.section = section
                exc.key = key
                exc.value = new_value
                raise exc

        setattr(conf_class_inst, key, new_value)

    # parse the configuration classes in order to collect all schemas
    # which were not overwritten by the config file
    for section, cflet in _conf_map.items():
        for key, value in cflet.__dict__.items():
            if isinstance(value, schema):
                if value.required:
                    raise RequiredKeyError(key)
                setattr(cflet, key, value.default)


def parse(conf_file=None, parser=None, type_check=True):
    """Parse a configuration file in order to overwrite the previously
    registered configuration classes.

    Params:

    - (str|file) conf_file: a path to a configuration file or an
      existing file-like object.

    - (callable) parser: the function parsing the configuration file
      and converting it to a dict.  If None a default parser will
      be picked up depending on the file extension.

    - (bool) type_check: when True raises exception in case an option
      specified in the configuration file has a different type than
      the one defined in the configuration class.
    """
    global _conf_file
    if _conf_file is not None:
        raise Error('already configured (you may want to use discard() '
                    'then call parse() again')
    if conf_file is not None:
        if isinstance(conf_file, basestring):
            # 'r' looks mandatory on Python 3.X
            file = open(conf_file, 'r')
        with file:
            pmap = {'.yaml': parse_yaml,
                    '.yml': parse_yaml,
                    '.toml': parse_toml,
                    '.json': parse_json,
                    # '.ini': parse_ini  # TODO
                    }
            if parser is None:
                if not hasattr(file, 'name'):
                    raise ValueError("can't determine format from a file "
                                     "object with no 'name' attribute")
                try:
                    ext = os.path.splitext(file.name)[1]
                    parser = pmap[ext]
                except KeyError:
                    raise ValueError("don't know how to parse %r" % file.name)
            file_conf = parser(file)

        # TODO: use a copy of _conf_map and set it at the end of this
        #       procedure?
        # TODO: should we use threading.[R]Lock (probably safer)?
        if isinstance(file_conf, dict):
            _process_conf(file_conf, type_check)
        else:
            # empty conf file
            if file_conf is not None:
                raise Error('invalid configuration file %r' % file.name)

    if conf_file is not None:
        _conf_file = file


def discard():
    """Discard previous configuration (if any)."""
    global _conf_file
    _conf_map.clear()
    _conf_file = None
