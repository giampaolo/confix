import errno
import imp
import io
import json
import os
import sys
import textwrap
import warnings
try:
    import configparser  # py3
except ImportError:
    import ConfigParser as configparser

import toml  # requires "pip install toml"
import yaml  # requires "pip install pyyaml"

import confix
from confix import Error, UnrecognizedKeyError, RequiredKeyError
from confix import istrue, isin, isnotin, isemail, get_parsed_conf
from confix import register, parse, parse_with_envvars, discard, schema
from confix import TypesMismatchError, AlreadyParsedError, NotParsedError
from confix import ValidationError, AlreadyRegisteredError


PY3 = sys.version_info >= (3, )
if PY3:
    StringIO = io.StringIO
else:
    from cStringIO import StringIO

if sys.version_info >= (2, 7):
    import unittest
else:
    import unittest2 as unittest  # requires 'pip install unittest2'


THIS_MODULE = os.path.splitext(os.path.basename(__file__))[0]
TESTFN = '$testfile'


def safe_remove(path):
    try:
        os.remove(path)
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise


# ===================================================================
# base test case and mixin class
# ===================================================================


class BaseTestCase(unittest.TestCase):

    def setUp(self):
        discard()
        self.original_environ = os.environ.copy()
        if getattr(self, 'TESTFN', None) is not None:
            safe_remove(self.TESTFN)

    def tearDown(self):
        discard()
        os.environ = self.original_environ
        if getattr(self, 'TESTFN', None) is not None:
            safe_remove(self.TESTFN)

    @classmethod
    def write_to_file(cls, content, fname=None):
        with open(fname or cls.TESTFN, 'w') as f:
            f.write(content)

    def parse(self, *args, **kwargs):
        parse(*args, **kwargs)

    def parse_with_envvars(self, *args, **kwargs):
        parse_with_envvars(*args, **kwargs)


class BaseMixin(object):
    """Base class from which mixin classes are derived."""
    TESTFN = None
    section = None

    def setUp(self):
        super(BaseMixin, self).setUp()
        self.original_section = self.section

    def tearDown(self):
        super(BaseMixin, self).tearDown()
        self.section = self.original_section

    def dict_to_file(self, dct):
        raise NotImplementedError('must be implemented in subclass')

    # --- base tests

    def test_empty_conf_file(self):
        @register(self.section)
        class config:
            foo = 1
            bar = 2

        self.write_to_file("   ")
        self.parse(self.TESTFN)
        assert config.foo == 1
        assert config.bar == 2

    def test_conf_file_overrides_key(self):
        # Conf file overrides one key, other one should be default.
        @register(self.section)
        class config:
            foo = 1
            bar = 2

        self.dict_to_file(
            dict(foo=5)
        )
        self.parse(self.TESTFN)
        assert config.foo == 5
        assert config.bar == 2

    def test_conf_file_overrides_all_keys(self):
        # Conf file overrides both keys.
        @register(self.section)
        class config:
            foo = 1
            bar = 2

        self.dict_to_file(
            dict(foo=5, bar=6)
        )
        self.parse(self.TESTFN)
        assert config.foo == 5
        assert config.bar == 6

    def test_unrecognized_key(self):
        # Conf file has a key which is not specified in the config class.
        @register(self.section)
        class config:
            foo = 1
            bar = 2

        self.dict_to_file(
            dict(foo=5, apple=6)
        )
        with self.assertRaises(UnrecognizedKeyError) as cm:
            self.parse(self.TESTFN)
        assert cm.exception.section == self.section
        assert cm.exception.key, 'apple'

    def test_types_mismatch(self):
        # Conf file provides a key with a value whose type is != than
        # conf class default type.
        @register(self.section)
        class config:
            foo = 1
            bar = 2

        self.dict_to_file(
            dict(foo=5, bar='foo')
        )
        with self.assertRaises(TypesMismatchError) as cm:
            self.parse(self.TESTFN)
        assert cm.exception.section == self.section
        assert cm.exception.key == 'bar'
        assert cm.exception.default_value == 2
        assert cm.exception.new_value == 'foo'

        # ...Unless we explicitly tell parse() to ignore type mismatch.
        self.parse(self.TESTFN, type_check=False)
        assert config.foo == 5
        assert config.bar == 'foo'

    def test_base_types(self):
        # str, int, float, bool are supposed to be supported by all
        # file formats.
        @register(self.section)
        class config:
            some_true_bool = True
            some_false_bool = False
            some_int = 0
            some_str = "foo"

        self.dict_to_file(dict(
            some_true_bool=False,
            some_false_bool=True,
            some_int=1,
            some_str="bar",
        ))
        self.parse(self.TESTFN)
        assert config.some_true_bool is False
        assert config.some_false_bool is True
        assert config.some_int == 1
        assert config.some_str == "bar"

    # def test_invalid_yaml_file(self):
    #     self.dict_to_file('?!?')
    #     with self.assertRaises(Error) as cm:
    #         self.parse(self.TESTFN)

    # --- test schemas

    def test_schema_base(self):
        # A schema with no constraints is supposed to be converted into
        # its default value after parse().
        @register(self.section)
        class config:
            foo = schema(10)

        self.dict_to_file({})
        self.parse(self.TESTFN)
        assert config.foo == 10

    def test_schema_required(self):
        # If a schema is required and it's not specified in the config
        # file expect an error.
        @register(self.section)
        class config:
            foo = schema(10, required=True)
            bar = 2

        self.dict_to_file(
            dict(bar=2)
        )
        with self.assertRaises(RequiredKeyError) as cm:
            self.parse(self.TESTFN)
        assert cm.exception.section == self.section
        assert cm.exception.key == 'foo'

    def test_schema_required_provided(self):
        # If a schema is required and it's provided in the conf file
        # eveything is cool.
        @register(self.section)
        class config:
            foo = schema(10, required=True)

        self.dict_to_file(
            dict(foo=5)
        )
        self.parse(self.TESTFN)
        assert config.foo == 5

    def test_schemas_w_multi_validators(self):
        def fun1(x):
            flags.append(1)
            return True

        def fun2(x):
            flags.append(2)
            return True

        def fun3(x):
            flags.append(3)
            return True

        def fun4(x):
            flags.append(4)
            return True

        @register(self.section)
        class config:
            overridden = schema(10, validator=[fun1, fun2])
            not_overridden = schema(10, validator=[fun3, fun4])

        flags = []
        self.dict_to_file(
            dict(overridden=5)
        )
        self.parse(self.TESTFN)
        assert sorted(flags) == [1, 2, 3, 4]
        assert config.overridden == 5
        assert config.not_overridden == 10

    # --- test validators

    def test_validator_ok(self):
        @register(self.section)
        class config:
            foo = schema(10, validator=lambda x: isinstance(x, int))

        self.dict_to_file(
            dict(foo=5)
        )
        self.parse(self.TESTFN)

    def test_validator_ko(self):
        @register(self.section)
        class config:
            foo = schema(10, validator=lambda x: isinstance(x, str))

        self.dict_to_file(
            dict(foo=5)
        )
        with self.assertRaises(ValidationError) as cm:
            self.parse(self.TESTFN)
        assert cm.exception.section == self.section
        assert cm.exception.key == 'foo'
        assert cm.exception.value == 5

    def test_validator_ko_custom_exc_w_message(self):
        def validator(value):
            raise ValidationError('message')

        @register(self.section)
        class config:
            foo = schema(10, validator=validator)
        self.dict_to_file(
            dict(foo=5)
        )

        with self.assertRaises(ValidationError) as cm:
            self.parse(self.TESTFN)
        # assert cm.exception.section == 'name'  # TOD)
        assert cm.exception.key == 'foo'
        assert cm.exception.value == 5
        assert cm.exception.msg == 'message'

    def test_validator_ko_custom_exc_w_no_message(self):
        def validator(value):
            raise ValidationError

        @register(self.section)
        class config:
            foo = schema(10, validator=validator)
        self.dict_to_file(
            dict(foo=5)
        )

        with self.assertRaises(ValidationError) as cm:
            self.parse(self.TESTFN)
        assert cm.exception.section == self.section
        assert cm.exception.key == 'foo'
        assert cm.exception.value == 5
        assert cm.exception.msg is None
        assert 'with value 5' in str(cm.exception)

    # --- test parse_with_envvars

    def test_envvars_w_file(self):
        # Test both config file and env vars are taken into account.
        @register(self.section)
        class config:
            foo = 1
            bar = 2
            apple = 3

        self.dict_to_file(
            dict(foo=5)
        )
        os.environ['APPLE'] = '10'
        self.parse_with_envvars(self.TESTFN)
        assert config.foo == 5
        assert config.bar == 2
        assert config.apple == 10

    def test_envvars_precendence_order(self):
        # Test env var takes precedence over config file.
        @register(self.section)
        class config:
            foo = 1

        self.dict_to_file(
            dict(foo=5)
        )
        os.environ['FOO'] = '6'
        self.parse_with_envvars(self.TESTFN)
        assert config.foo == 6

    def test_envvars_case_sensitive(self):
        @register(self.section)
        class config:
            foo = 1
            bar = 2
            APPLE = 3

        # non-uppercase env vars are supposed to be ignored
        os.environ['FoO'] = '10'
        os.environ['BAR'] = '20'
        os.environ['APPLE'] = '30'
        parse_with_envvars(case_sensitive=True)
        assert config.foo == 1
        assert config.bar == 2
        assert config.APPLE == 30

    def test_envvars_case_insensitive(self):
        @register(self.section)
        class config:
            foo = 1
            bar = 2
            APPLE = 3
            PeAr = 4

        # non-uppercase env vars are supposed to be ignored
        os.environ['FoO'] = '10'
        os.environ['BAR'] = '20'
        os.environ['APPLE'] = '30'
        os.environ['PEAR'] = '40'
        parse_with_envvars(case_sensitive=False)
        assert config.foo == 1
        assert config.bar == 20
        assert config.APPLE == 30
        assert config.PeAr == 40

    def test_envvars_type_mismatch(self):
        @register(self.section)
        class config:
            some_int = 1
            some_float = 0.1
            some_bool = True

        # int
        os.environ['SOME_INT'] = 'foo'
        with self.assertRaises(TypesMismatchError) as cm:
            parse_with_envvars()
        assert cm.exception.section == self.section
        assert cm.exception.key == 'some_int'
        assert cm.exception.default_value == 1
        assert cm.exception.new_value == 'foo'
        del os.environ['SOME_INT']

        # float
        os.environ['SOME_FLOAT'] = 'foo'
        with self.assertRaises(TypesMismatchError) as cm:
            parse_with_envvars()
        assert cm.exception.section == self.section
        assert cm.exception.key == 'some_float'
        assert cm.exception.default_value == 0.1
        assert cm.exception.new_value == 'foo'
        del os.environ['SOME_FLOAT']

        # bool
        os.environ['SOME_BOOL'] = 'foo'
        with self.assertRaises(TypesMismatchError) as cm:
            parse_with_envvars()
        assert cm.exception.section == self.section
        assert cm.exception.key == 'some_bool'
        assert cm.exception.default_value is True
        assert cm.exception.new_value == 'foo'

    # --- test multiple sections

    def test_multisection_multiple(self):
        # Define two configuration classes, control them via a single
        # conf file defining separate sections.
        self.section = None

        @register('ftp')
        class ftp_config:
            port = 21
            username = 'ftp'

        @register('http')
        class http_config:
            port = 80
            username = 'www'

        self.dict_to_file({
            'ftp': dict(username='foo'),
            'http': dict(username='bar'),
        })
        self.parse(self.TESTFN)
        assert ftp_config.port == 21
        assert ftp_config.username == 'foo'
        assert http_config.port == 80
        assert http_config.username == 'bar'

    def test_multisection_invalid_section(self):
        # Config file define a section which is not defined in config
        # class.
        self.section = None

        @register('ftp')
        class config:
            port = 21
            username = 'ftp'

        self.dict_to_file({
            'http': dict(username='bar'),
        })
        with self.assertRaises(UnrecognizedKeyError) as cm:
            self.parse(self.TESTFN)
        assert cm.exception.key == 'http'
        assert cm.exception.new_value == dict(username='bar')
        assert cm.exception.section is None

    def test_multisection_unrecognized_key(self):
        # Config file define a section key which is not defined in config
        # class.
        self.section = None

        @register('ftp')
        class config:
            port = 21
            username = 'ftp'

        self.dict_to_file({
            'ftp': dict(password='bar'),
        })
        with self.assertRaises(UnrecognizedKeyError) as cm:
            self.parse(self.TESTFN)
        assert cm.exception.key == 'password'
        assert cm.exception.new_value == 'bar'
        assert cm.exception.section == 'ftp'


# ===================================================================
# mixin tests
# ===================================================================

# yaml

class TestYamlMixin(BaseMixin, BaseTestCase):
    TESTFN = TESTFN + '.yaml'

    def dict_to_file(self, dct):
        if self.section:
            dct = {self.section: dct}
        s = yaml.dump(dct, default_flow_style=False)
        self.write_to_file(s)


class TestYamlWithSectionMixin(TestYamlMixin):
    section = 'name'


# json

class TestJsonMixin(BaseMixin, BaseTestCase):
    TESTFN = TESTFN + '.json'

    def dict_to_file(self, dct):
        if self.section:
            dct = {self.section: dct}
        self.write_to_file(json.dumps(dct))


class TestJsonWithSectionMixin(TestJsonMixin):
    section = 'name'


# toml

class TestTomlMixin(BaseMixin, BaseTestCase):
    TESTFN = TESTFN + '.toml'

    def dict_to_file(self, dct):
        if self.section:
            dct = {self.section: dct}
        s = toml.dumps(dct)
        self.write_to_file(s)


class TestTomWithSectionlMixin(TestTomlMixin):
    section = 'name'


# ini

class TestIniMixin(BaseMixin, BaseTestCase):
    TESTFN = TESTFN + 'testfile.ini'
    section = 'name'

    def dict_to_file(self, dct):
        if not self._testMethodName.startswith('test_multisection'):
            dct = {self.section: dct}
        config = configparser.RawConfigParser()
        for section, values in dct.items():
            assert isinstance(section, str)
            config.add_section(section)
            for key, value in values.items():
                config.set(section, key, value)
        fl = StringIO()
        config.write(fl)
        fl.seek(0)
        content = fl.read()
        self.write_to_file(content)


# env vars

class TestEnvVarsMixin(BaseMixin, BaseTestCase):
    TESTFN = TESTFN + 'testfile.ini'

    def setUp(self):
        super(TestEnvVarsMixin, self).setUp()
        if self._testMethodName.startswith('test_multisection'):
            raise unittest.SkipTest

    def parse(self, *args, **kwargs):
        parse_with_envvars(**kwargs)

    def parse_with_envvars(self, *args, **kwargs):
        parse_with_envvars(**kwargs)

    def dict_to_file(self, dct):
        for k, v in dct.items():
            os.environ[k.upper()] = str(v)

    @unittest.skip("")
    def test_unrecognized_key(self):
        # Will fail because var names not matching the default conf
        # keys are skipped.
        pass


# ===================================================================
# tests for a specific format
# ===================================================================


class TestIni(BaseTestCase):
    TESTFN = TESTFN + '.ini'

    def test_sectionless_conf(self):
        @register()
        class config:
            foo = 1

        self.write_to_file("")
        self.assertRaisesRegexp(
            Error,
            "can't parse ini files if a sectionless configuration class",
            parse, self.TESTFN)

    def test_true_type(self):
        for value in ("1", "yes", "true", "on", "YES", "TRUE", "ON"):
            @register('name')
            class config:
                foo = False

            self.write_to_file(textwrap.dedent("""
                [name]
                foo = %s
            """ % (value)))
            self.parse(self.TESTFN)
            assert config.foo is True
            discard()

    def test_false_type(self):
        for value in ("0", "no", "false", "off", "NO", "FALSE", "OFF"):
            @register('name')
            class config:
                foo = True

            self.write_to_file(textwrap.dedent("""
                [name]
                foo = %s
            """ % (value)))
            self.parse(self.TESTFN)
            assert config.foo is False
            discard()


class TestEnvVars(BaseTestCase):

    def test_true_type(self):
        for value in ("1", "yes", "true", "on", "YES", "TRUE", "ON"):
            @register()
            class config:
                foo = False

            os.environ['FOO'] = value
            self.parse_with_envvars()
            assert config.foo is True
            discard()

    def test_false_type(self):
        for value in ("0", "no", "false", "off", "NO", "FALSE", "OFF"):
            @register('name')
            class config:
                foo = True

            os.environ['FOO'] = value
            self.parse_with_envvars()
            assert config.foo is False
            discard()


# ===================================================================
# test validators
# ===================================================================


class TestValidators(BaseTestCase):

    def test_istrue(self):
        assert istrue('foo')
        self.assertRaises(ValidationError, istrue, '')

    def test_isin(self):
        self.assertRaises(TypeError, isin, 1)
        fun = isin(('1', '2'))
        assert fun('1')
        assert fun('2')
        self.assertRaises(ValidationError, fun, '3')
        self.assertRaises(ValueError, isin, [])

    def test_isnotin(self):
        self.assertRaises(TypeError, isin, 1)
        fun = isnotin(('1', '2'))
        assert fun('3')
        assert fun('4')
        self.assertRaises(ValidationError, fun, '2')
        self.assertRaisesRegexp(
            TypeError, "is not iterable", isnotin, None)
        self.assertRaisesRegexp(
            ValueError, "sequence can't be empty", isnotin, [])

    def test_isemail(self):
        assert isemail("foo@bar.com")
        assert isemail("foo@gmail.bar.com")
        self.assertRaises(ValidationError, isemail, "@bar.com")
        self.assertRaises(ValidationError, isemail, "foo@bar")
        self.assertRaises(ValidationError, isemail, "foo@bar.")
        self.assertRaisesRegexp(
            ValidationError, "expected a string", isemail, None)
        assert isemail("email@domain.com")
        assert isemail("\"email\"@domain.com")
        assert isemail("firstname.lastname@domain.com")
        assert isemail("email@subdomain.domain.com")
        assert isemail("firstname+lastname@domain.com")
        assert isemail("email@123.123.123.123")
        assert isemail("email@[123.123.123.123]")
        assert isemail("1234567890@domain.com")
        assert isemail("email@domain-one.com")
        assert isemail("_______@domain.com")
        assert isemail("email@domain.name")
        assert isemail("email@domain.co.jp")
        assert isemail("firstname-lastname@domain.com")


# ===================================================================
# parse() tests
# ===================================================================


class TestParse(BaseTestCase):

    def test_no_conf_file(self):
        # parse() is supposed to parse also if no conf file is passed
        @register()
        class config:
            foo = 1
            bar = schema(10)

        parse()
        assert config.foo == 1
        assert config.bar == 10

    def test_conf_file_w_unknown_ext(self):
        # Conf file with unsupported extension.
        with open(TESTFN, 'w') as f:
            f.write('foo')
        self.addCleanup(safe_remove, TESTFN)
        with self.assertRaises(ValueError) as cm:
            parse(TESTFN)
        assert "don't know how to parse" in str(cm.exception)
        assert "extension not supported" in str(cm.exception)

    def test_parser_with_no_file(self):
        self.assertRaises(ValueError, parse, file_parser=lambda x: {})

    def test_no_registered_class(self):
        self.assertRaises(Error, parse)

    def test_file_like(self):
        @register()
        class foo:
            foo = 1

        file = io.StringIO()
        with self.assertRaises(Error) as cm:
            parse(file)
        assert str(cm.exception) == \
            "can't determine file format from a file object with no 'name' " \
            "attribute"

        assert str(cm.exception) == \
            "can't determine file format from a file object with no 'name' " \
            "attribute"

        file = io.StringIO()
        parse(file, file_parser=lambda x: {})

    def test_parse_called_twice(self):
        @register()
        class config:
            foo = 1
            bar = 2

        parse()
        self.assertRaises(AlreadyParsedError, parse)
        self.assertRaises(AlreadyParsedError, parse_with_envvars)


# ===================================================================
# schema() tests
# ===================================================================


class TestSchema(BaseTestCase):

    def test_errors(self):
        # no default nor required=True
        self.assertRaisesRegexp(
            ValueError, "specify a default value or set required", schema)
        # not callable validator
        self.assertRaisesRegexp(
            TypeError, "not callable", schema, default=10, validator=1)
        self.assertRaisesRegexp(
            TypeError, "not callable", schema, default=10, validator=['foo'])

# ===================================================================
# exception classes tests
# ===================================================================


class TestExceptions(BaseTestCase):

    def test_error(self):
        exc = Error('foo')
        assert str(exc) == 'foo'
        assert repr(exc) == 'foo'

    def test_already_parsed_error(self):
        exc = AlreadyParsedError()
        assert 'already parsed' in str(exc)

    def test_already_registered_error(self):
        exc = AlreadyRegisteredError('foo')
        assert 'already registered' in str(exc)
        assert 'foo' in str(exc)

    def test_not_parsed_error(self):
        exc = NotParsedError()
        assert 'not parsed' in str(exc)

    def test_unrecognized_key_error(self):
        exc = UnrecognizedKeyError(section=None, key='foo', new_value='bar')
        assert str(exc) == \
            "config file provides key 'foo' with value 'bar' but key 'foo' " \
            "is not defined in any of the config classes"

    def test_required_key_error(self):
        exc = RequiredKeyError(None, key="foo")
        assert str(exc) == \
            "configuration class requires 'foo' key to be specified via " \
            "config file or environment variable"

    def test_types_mismatch_error(self):
        exc = TypesMismatchError(
            section=None, key="foo", default_value=1, new_value='bar')
        assert str(exc) == \
            "type mismatch for key 'foo' (default_value=1, %s) got " \
            "'bar' (%s)" % (type(1), type(""))


# ===================================================================
# get_parsed_conf() tests
# ===================================================================


class TestGetParsedConf(BaseTestCase):

    def test_root_only(self):
        @register()
        class root_conf:
            root_value = 1

        self.assertRaises(NotParsedError, get_parsed_conf)
        parse()
        assert get_parsed_conf() == {'root_value': 1}

    def test_root_plus_sub(self):
        @register()
        class root_conf:
            root_value = 1

        @register('sub')
        class sub_conf:
            sub_value = 1

        parse()
        assert get_parsed_conf() == {'root_value': 1, 'sub': {'sub_value': 1}}

    def test_sub_plus_root(self):
        @register('sub')
        class sub_conf:
            sub_value = 1

        @register()
        class root_conf:
            root_value = 1

        parse()
        assert get_parsed_conf() == {'root_value': 1, 'sub': {'sub_value': 1}}

    def test_hidden_key(self):
        @register()
        class config:
            foo = 1
            _hidden = 2

        parse()
        assert get_parsed_conf() == {'foo': 1}


# ===================================================================
# @register() tests
# ===================================================================


class TestRegister(BaseTestCase):

    def test_dictify_and_method(self):
        @register()
        class config:
            foo = 1
            bar = 2
            _hidden = 3

            @classmethod
            def some_method(cls):
                return 1

        assert dict(config) == {'foo': 1, 'bar': 2}
        assert config.some_method() == 1
        parse()
        assert dict(config) == {'foo': 1, 'bar': 2}
        assert config.some_method() == 1

    def test_special_methods(self):
        @register()
        class config:
            """docstring"""
            foo = 1
            bar = 2

            @classmethod
            def some_method(cls):
                return 1

        assert config.__doc__ == "docstring"
        assert config.__name__ == "config"
        # __len__
        assert len(config) == 2
        # __getitem__
        assert config['foo'] == 1
        # __setitem__
        config['foo'] == 33
        assert config['foo'] == 1
        # __contains__
        assert 'foo' in config
        # should we allow this?
        assert 'some_method' in config
        # __delitem__
        del config['foo']
        assert 'foo' not in config
        assert len(config) == 1
        # __repr__
        repr(config)

    def test_register_twice(self):
        @register()
        class config:
            foo = 1

        with self.assertRaises(AlreadyRegisteredError):
            @register()
            class config_2:
                foo = 1

    def test_decorate_fun(self):
        with self.assertRaises(TypeError) as cm:
            @register()
            def foo():
                pass

        assert 'register decorator is supposed to be used against a class' in \
            str(cm.exception)

    def test_override_root_section_key(self):
        @register()
        class root:
            foo = 1

        with self.assertRaises(Error) as cm:
            @register(section="foo")
            class sub:
                bar = 2

        assert "previously registered root class" in str(cm.exception)
        assert "already defines a key with the same name" in str(cm.exception)

    def test_register_after_parse(self):
        @register()
        class config:
            foo = 1

        parse()

        with warnings.catch_warnings(record=True) as ws:
            @register(section="unparsed")
            class unparsed_config:
                bar = 1

        assert len(ws) == 1
        assert 'configuration class defined after parse' in \
            str(ws[0].message)
        assert ws[0].category is UserWarning
        # global conf will not include this
        assert get_parsed_conf() == {'foo': 1}
        # but it's still a magic object
        assert dict(unparsed_config) == {'bar': 1}

    def test_invalid_section_type(self):
        # this also serves as a test for
        with self.assertRaises(TypeError):
            @register(section=1)
            class config:
                foo = 1

    def test_invalid_section_str(self):
        with self.assertRaises(ValueError):
            @register(section="")
            class config:
                foo = 1


# ===================================================================
# misc tests
# ===================================================================


class TestMisc(BaseTestCase):

    def test_mro(self):
        # This method is automatically added by the meta class wrapper:
        # https://docs.python.org/3/library/stdtypes.html#class.mro
        # Make sure we can override it.
        @register()
        class config:
            mro = 2

        assert config.mro == 2

        discard()

        @register()
        class config:
            pass

        config.mro

    def test__all__(self):
        dir_confix = dir(confix)
        for name in dir_confix:
            if name in ('configparser', 'logger', 'basestring'):
                continue
            if not name.startswith('_'):
                try:
                    __import__(name)
                except ImportError:
                    if name not in confix.__all__:
                        fun = getattr(confix, name)
                        if fun is None:
                            continue
                        if (fun.__doc__ is not None and
                                'deprecated' not in fun.__doc__.lower()):
                            self.fail('%r not in confix.__all__' % name)

        # Import 'star' will break if __all__ is inconsistent, see:
        # https://github.com/giampaolo/psutil/issues/656
        # Can't do `from confix import *` as it won't work on python 3
        # so we simply iterate over __all__.
        for name in confix.__all__:
            assert name in dir_confix

    def test_version(self):
        assert '.'.join([str(x) for x in confix.version_info]) == \
            confix.__version__

    def test_setup_script(self):
        here = os.path.abspath(os.path.dirname(__file__))
        setup_py = os.path.realpath(os.path.join(here, 'setup.py'))
        module = imp.load_source('setup', setup_py)
        self.assertRaises(SystemExit, module.setup)
        assert module.get_version() == confix.__version__


def main():
    verbosity = 1 if 'TOX' in os.environ else 2
    unittest.main(verbosity=verbosity)


if __name__ == '__main__':
    main()
