#!/usr/bin/env python

"""
A language-agnostic configuration parser.
Currently supports YAML, JSON, INI and TOML serialization formats.
"""

import collections
import json
import os
import sys

try:
    import configparser  # python 3
except ImportError:     #python 2
    import ConfigParser as configparser


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

    def __init__(self, section, key, msg=None):
        self.section = section
        self.key = key
        self.msg = msg

    def __str__(self):
        return self.msg or \
            "%r configuration class has no value %r but this is defined" \
            " in the config file" % (self.section, self.key)


class RequiredKeyError(Error):
    """Raised when the config file didn't specify a required key."""

    def __init__(self, section, key, msg=None):
        self.section = section
        self.key = key
        self.msg = msg

    def __str__(self):
        return self.msg or \
            "%r configuration class requires %r key to be specified in the " \
            "config file" % (self.section, self.key)


class TypesMismatchError(Error):
    """Raised when config file overrides a key having a type different
    than the original one defined in the configuration class.
    """

    def __init__(self, section, key, default_value, new_value, msg=None):
        self.section = section
        self.key = key
        self.default_value = default_value
        self.new_value = new_value
        self.msg = msg

    def __str__(self):
        # TODO: rephrase
        return "'%s:%s' type mismatch expected %r, got %r" \
            % (self.section, self.key,
               type(self.default_value), type(self.new_value))


# --- parsers
#root = os.path.curdir

    
def parse_yaml(file):
    import yaml
    import copy
    
    ## define custom yaml tag handler
    def join(loader, node):
        seq = loader.construct_sequence(node)
        return ''.join([str(i) for i in seq])
    
    ## register the yaml tag handler
    yaml.add_constructor('!join', join)
    
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


def parse_ini(file):
    config = configparser.ConfigParser()
    config.read(file.name)
    ret = {}
    bool_true = set(("1", "yes", "true", "on"))
    bool_false = set(("0", "no", "false", "off"))
    for section, values in config._sections.items():
        ret[section] = {}
        for key, value in values.items():
            value_stripped = value.strip()
            if value.isdigit():
                value = int(value)
            elif value_stripped in bool_true:
                value = True
            elif value_stripped in bool_false:
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


# --- public API

_conf_map = {}
#_conf_file = None
#_DEFAULT = object()


class schema(collections.namedtuple('field',
             ['default', 'required', 'validator'])):

    def __new__(cls, default=object(), required=False, validator=None):
        if not required and default is object():
            raise TypeError("specify a default value or set required=True")
        if validator is not None and not callable(validator):
            raise ValueError("%r is not callable" % validator)
        return super(schema, cls).__new__(cls, default, required, validator)


def register(name):
    """Register a configuration class which will be parsed later."""
    def wrapper(klass):
        _conf_map[name] = klass
        return klass
    return wrapper


def parse(conf_file, parser=None, type_check=True):
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
    #global _conf_file
    #if _conf_file is not None:
    #    discard()
        #raise Error('already configured (you may want to use discard() '
        #            'then call parse() again')
    if isinstance(conf_file, basestring):
        # 'r' looks mandatory on Python 3.X
        file = open(conf_file, 'rb')
    with file:
        pmap = {'.yaml': parse_yaml,
                '.yml': parse_yaml,
                '.toml': parse_toml,
                '.json': parse_json,
                '.ini': parse_ini}
        if parser is None:
            if not hasattr(file, 'name'):
                raise ValueError("can't determine format from a file object "
                                 "with no 'name' attribute")
            try:
                ext = os.path.splitext(file.name)[1]
                parser = pmap[ext]
            except KeyError:
                raise ValueError("don't know how to parse %r" % file.name)
        conf = parser(file)

        file.close()
        
    # TODO: use a copy of _conf_map and set it at the end of this
    #       procedure?
    # TODO: should we use threading.[R]Lock (probably safer)?
    if isinstance(conf, dict):
        for section, values in conf.items():
            inst = _conf_map.get(section, None)
            if inst is not None:
                assert isinstance(values, dict)
                for key, new_value in values.items():
                    #
                    try:
                        default_value = getattr(inst, key)
                    except AttributeError:
                        raise InvalidKeyError(section, key)
                    #
                    is_schema = isinstance(default_value, schema)
                    # TODO: perhpas "not is_schema" is not necessary
                    #value of None is workaround to avoid type checking
                    if default_value != None:
                        check_type = (type_check
                                      and not is_schema
                                      and default_value is not None
                                      and new_value is not None)
                        if check_type and type(new_value) != type(default_value):
                            #check if class is correct but not instantiated from late binding, if so don't raise error
                            if check_type and type(new_value.__class__) is not type(default_value):
                                raise TypesMismatchError(section, key, default_value,
                                                         new_value)
                    #
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
                            exc.section = section
                            exc.key = key
                            exc.value = new_value
                            raise exc

                    setattr(inst, key, new_value)
    else:
        if conf is not None:
            raise Error('invalid configuration file %r' % file.name)

    # parse the configuration classes in order to collect all schemas
    # which were not overwritten by the config file
    for section, cflet in _conf_map.items():
        for key, value in cflet.__dict__.items():
            if isinstance(value, schema):
                if value.required:
                    raise RequiredKeyError(section, key)
                setattr(cflet, key, value.default)
    #_conf_file = file
    #print('current map' + str(_conf_map))


# def discard():
#     """Discard previous configuration (if any)."""
#     global _conf_file
#     #don't clear this so that we can have multiple config files
#     #_conf_map.clear()
#     _conf_file = None
