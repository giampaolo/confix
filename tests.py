# TODO:
# -test parse()'s 'format' parameter

import errno
import io
import json
import os
import sys
# import textwrap
# try:
#     import configparser  # py3
# except ImportError:
#     import ConfigParser as configparser

from confix import Error, UnrecognizedKeyError, RequiredKeyError
from confix import register, parse, parse_with_envvars, discard, schema
from confix import TypesMismatchError, AlreadyParsedError
from confix import ValidationError

try:
    import toml
except ImportError:
    toml = None
try:
    import yaml
except ImportError:
    yaml = None

PY3 = sys.version_info >= (3, )
# if PY3:
#     import io
#     StringIO = io.StringIO
# else:
#     from StringIO import StringIO

if sys.version_info >= (2, 7):
    import unittest
else:
    import unittest2 as unittest  # requires 'pip install unittest2'


THIS_MODULE = os.path.splitext(os.path.basename(__file__))[0]
TESTFN = '$testfile'


def unlink(path):
    try:
        os.remove(path)
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise


# ===================================================================
# base class
# ===================================================================


class TestBase(object):
    """Base class from which mixin classes are derived."""
    TESTFN = None

    def tearDown(self):
        discard()
        unlink(self.TESTFN)

    @classmethod
    def tearDownClass(cls):
        unlink(TESTFN)

    # --- utils

    def dict_to_file(self, dct):
        raise NotImplementedError('must be implemented in subclass')

    @classmethod
    def write_to_file(cls, content, fname=None):
        with open(fname or cls.TESTFN, 'w') as f:
            f.write(content)

    # --- base tests

    def test_empty_conf_file(self):
        @register()
        class config:
            foo = 1
            bar = 2

        self.write_to_file("   ")
        parse(self.TESTFN)
        self.assertEqual(config.foo, 1)
        self.assertEqual(config.bar, 2)

    def test_no_conf_file(self):
        # parse() is supposed to parse also if no conf file is passed
        @register()
        class config:
            foo = 1
            bar = schema(10)

        parse()
        self.assertEqual(config.foo, 1)
        self.assertEqual(config.bar, 10)

    def test_conf_file_w_unknown_ext(self):
        # Conf file with unsupported extension.
        with open(TESTFN, 'w') as f:
            f.write('foo')
        self.addCleanup(unlink, TESTFN)
        with self.assertRaises(ValueError) as cm:
            parse(TESTFN)
        self.assertIn("don't know how to parse", str(cm.exception))
        self.assertIn("extension not supported", str(cm.exception))

    def test_conf_file_overrides_key(self):
        # Conf file overrides one key, other one should be default.
        @register()
        class config:
            foo = 1
            bar = 2

        self.dict_to_file(
            dict(foo=5)
        )
        parse(self.TESTFN)
        self.assertEqual(config.foo, 5)
        self.assertEqual(config.bar, 2)

    def test_conf_file_overrides_all_keys(self):
        # Conf file overrides both keys.
        @register()
        class config:
            foo = 1
            bar = 2

        self.dict_to_file(
            dict(foo=5, bar=6)
        )
        parse(self.TESTFN)
        self.assertEqual(config.foo, 5)
        self.assertEqual(config.bar, 6)

    def test_unrecognized_key(self):
        # Conf file has a key which is not specified in the config class.
        @register()
        class config:
            foo = 1
            bar = 2

        self.dict_to_file(
            dict(foo=5, apple=6)
        )
        with self.assertRaises(UnrecognizedKeyError) as cm:
            parse(self.TESTFN)
        # self.assertEqual(cm.exception.section, 'name')  # TODO
        self.assertEqual(cm.exception.key, 'apple')

    def test_types_mismatch(self):
        # Conf file provides a key with a value whose type is != than
        # conf class default type.
        @register()
        class config:
            foo = 1
            bar = 2

        self.dict_to_file(
            dict(foo=5, bar='6')
        )
        with self.assertRaises(TypesMismatchError) as cm:
            parse(self.TESTFN)
        # self.assertEqual(cm.exception.section, 'name')
        self.assertEqual(cm.exception.key, 'bar')
        self.assertEqual(cm.exception.default_value, 2)
        self.assertEqual(cm.exception.new_value, '6')

        # ...Unless we explicitly tell parse() to ignore type mismatch.
        parse(self.TESTFN, type_check=False)
        self.assertEqual(config.foo, 5)
        self.assertEqual(config.bar, '6')

    # def test_invalid_yaml_file(self):
    #     self.dict_to_file('?!?')
    #     with self.assertRaises(Error) as cm:
    #         parse(self.TESTFN)

    def test_parse_called_twice(self):
        @register()
        class config:
            foo = 1
            bar = 2

        self.dict_to_file(
            dict(foo=5, bar=6)
        )
        parse(self.TESTFN)
        self.assertRaises(AlreadyParsedError, parse)
        self.assertRaises(AlreadyParsedError, parse_with_envvars)

    # --- test schemas

    def test_schema_base(self):
        # A schema with no constraints is supposed to be converted into
        # its default value after parse().
        @register()
        class config:
            foo = schema(10)

        self.dict_to_file({})
        parse(self.TESTFN)
        self.assertEqual(config.foo, 10)

    def test_schema_required(self):
        # If a schema is required and it's not specified in the config
        # file expect an error.
        @register()
        class config:
            foo = schema(10, required=True)
            bar = 2

        self.dict_to_file(
            dict(bar=2)
        )
        with self.assertRaises(RequiredKeyError) as cm:
            parse(self.TESTFN)
        # self.assertEqual(cm.exception.section, 'name')  # TODO
        self.assertEqual(cm.exception.key, 'foo')

    def test_schema_required_provided(self):
        # If a schema is required and it's provided in the conf file
        # eveything is cool.
        @register()
        class config:
            foo = schema(10, required=True)

        self.dict_to_file(
            dict(foo=5)
        )
        parse(self.TESTFN)
        self.assertEqual(config.foo, 5)

    def test_schema_errors(self):
        # no default nor required=True
        self.assertRaises(TypeError, schema)
        # not callable validator
        self.assertRaises(ValueError, schema, 10, False, 'foo')

    # --- test validators

    def test_validator_ok(self):
        @register()
        class config:
            foo = schema(10, validator=lambda x: isinstance(x, int))

        self.dict_to_file(
            dict(foo=5)
        )
        parse(self.TESTFN)

    def test_validator_ko(self):
        @register()
        class config:
            foo = schema(10, validator=lambda x: isinstance(x, str))

        self.dict_to_file(
            dict(foo=5)
        )
        with self.assertRaises(ValidationError) as cm:
            parse(self.TESTFN)
        # self.assertEqual(cm.exception.section, 'name')  # TODO
        self.assertEqual(cm.exception.key, 'foo')
        self.assertEqual(cm.exception.value, 5)

    def test_validator_ko_custom_exc_w_message(self):
        def validator(value):
            raise ValidationError('message')

        @register()
        class config:
            foo = schema(10, validator=validator)
        self.dict_to_file(
            dict(foo=5)
        )

        with self.assertRaises(ValidationError) as cm:
            parse(self.TESTFN)
        # self.assertEqual(cm.exception.section, 'name')  # TODO
        self.assertEqual(cm.exception.key, 'foo')
        self.assertEqual(cm.exception.value, 5)
        self.assertEqual(cm.exception.msg, 'message')

    def test_validator_ko_custom_exc_w_no_message(self):
        def validator(value):
            raise ValidationError

        @register()
        class config:
            foo = schema(10, validator=validator)
        self.dict_to_file(
            dict(foo=5)
        )

        with self.assertRaises(ValidationError) as cm:
            parse(self.TESTFN)
        # self.assertEqual(cm.exception.section, 'name')  # TODO
        self.assertEqual(cm.exception.key, 'foo')
        self.assertEqual(cm.exception.value, 5)
        self.assertEqual(cm.exception.msg, None)
        self.assertIn('(got 5)', str(cm.exception))

    # --- parse_with_envvars

    def test_envvars_base(self):
        @register()
        class config:
            foo = 1
            bar = 2
            apple = 3

        self.dict_to_file(
            dict(foo=5)
        )
        os.environ['APPLE'] = '10'
        parse_with_envvars(self.TESTFN)
        self.assertEqual(config.foo, 5)
        self.assertEqual(config.bar, 2)
        self.assertEqual(config.apple, 10)

    def test_envvars_base_case_sensitive(self):
        @register()
        class config:
            foo = 1
            bar = 2
            apple = 3

        self.dict_to_file(
            dict(foo=5)
        )
        os.environ['APPLE'] = '10'
        parse_with_envvars(self.TESTFN, case_sensitive=True)
        self.assertEqual(config.foo, 5)
        self.assertEqual(config.bar, 2)
        self.assertEqual(config.apple, 3)

    def test_envvars_convert_type(self):
        @register()
        class config:
            some_int = 1
            some_float = 1.0
            some_true_bool = True
            some_false_bool = True

        os.environ['SOME_INT'] = '2'
        os.environ['SOME_FLOAT'] = '2.0'
        os.environ['SOME_TRUE_BOOL'] = 'false'
        os.environ['SOME_FALSE_BOOL'] = 'true'
        parse_with_envvars()
        self.assertEqual(config.some_int, 2)
        self.assertEqual(config.some_float, 2.0)
        self.assertEqual(config.some_true_bool, False)
        self.assertEqual(config.some_false_bool, True)

    def test_envvars_type_mismatch(self):
        @register()
        class config:
            some_int = 1
            some_float = 0.1

        os.environ['SOME_INT'] = 'foo'
        with self.assertRaises(TypesMismatchError) as cm:
            parse_with_envvars()
        # self.assertEqual(cm.exception.section, 'name')
        self.assertEqual(cm.exception.key, 'some_int')
        self.assertEqual(cm.exception.default_value, 1)
        self.assertEqual(cm.exception.new_value, 'foo')

        del os.environ['SOME_INT']
        os.environ['SOME_FLOAT'] = 'foo'
        with self.assertRaises(TypesMismatchError) as cm:
            parse_with_envvars()
        # self.assertEqual(cm.exception.section, 'name')
        self.assertEqual(cm.exception.key, 'some_float')
        self.assertEqual(cm.exception.default_value, 0.1)
        self.assertEqual(cm.exception.new_value, 'foo')


# ===================================================================
# mixin tests
# ===================================================================

class TestJsonMixin(TestBase, unittest.TestCase):
    TESTFN = TESTFN + 'testfile.json'

    def dict_to_file(self, dct):
        self.write_to_file(json.dumps(dct))


@unittest.skipUnless(toml is not None, "toml module is not installed")
class TestTomlMixin(TestBase, unittest.TestCase):
    TESTFN = TESTFN + 'testfile.toml'

    def dict_to_file(self, dct):
        s = toml.dumps(dct)
        self.write_to_file(s)


@unittest.skipUnless(yaml is not None, "yaml module is not installed")
class TestYamlMixin(TestBase, unittest.TestCase):
    TESTFN = 'testfile.yaml'

    def dict_to_file(self, dct):
        s = yaml.dump(dct, default_flow_style=False)
        self.write_to_file(s)


# class TestIniMixin(TestBase, unittest.TestCase):
#     TESTFN = TESTFN + 'testfile.ini'

    # def dict_to_file(self, dct):
    #     config = configparser.RawConfigParser()
    #     for section, values in dct.items():
    #         assert isinstance(section, str)
    #         config.add_section(section)
    #         for key, value in values.items():
    #             config.set(section, key, value)
    #     fl = StringIO()
    #     config.write(fl)
    #     fl.seek(0)
    #     content = fl.read()
    #     self.write_to_file(content)


# ===================================================================
# tests for a specific format
# ===================================================================

# class TestIni(unittest.TestCase):
#     TESTFN = TESTFN + '.ini'

#     def tearDown(self):
#         discard()
#         unlink(self.TESTFN)

#     def write_to_file(self, content):
#         with open(self.TESTFN, 'w') as f:
#             f.write(content)

#     # XXX: should this test be common to all formats?
#     def test_int_ok(self):
#         @register('name')
#         class config:
#             foo = 1
#             bar = 2

#         self.write_to_file(textwrap.dedent("""
#             [name]
#             foo = 9
#         """))
#         parse(self.TESTFN)
#         self.assertEqual(config.foo, 9)

#     # XXX: should this test be common to all formats?
#     def test_int_ko(self):
#         @register('name')
#         class config:
#             foo = 1
#             bar = 2

#         self.write_to_file(textwrap.dedent("""
#             [name]
#             foo = '9'
#         """))
#         self.assertRaises(TypesMismatchError, parse, self.TESTFN)

#     def test_float(self):
#         @register('name')
#         class config:
#             foo = 1.1
#             bar = 2

#         self.write_to_file(textwrap.dedent("""
#             [name]
#             foo = 1.3
#         """))
#         parse(self.TESTFN)
#         self.assertEqual(config.foo, 1.3)

#     def test_true(self):
#         @register('name')
#         class config:
#             foo = None
#             bar = 2

#         true_values = ("1", "yes", "true", "on")
#         for value in true_values:
#             self.write_to_file(textwrap.dedent("""
#                 [name]
#                 foo = %s
#             """ % (value)))
#             parse(self.TESTFN)
#             self.assertEqual(config.foo, True)
#             discard()

#     def test_false(self):
#         @register('name')
#         class config:
#             foo = None
#             bar = 2

#         true_values = ("0", "no", "false", "off")
#         for value in true_values:
#             self.write_to_file(textwrap.dedent("""
#                 [name]
#                 foo = %s
#             """ % (value)))
#             parse(self.TESTFN)
#             self.assertEqual(config.foo, False)
#             discard()


# ===================================================================
# tests misc
# ===================================================================


class TestMisc(unittest.TestCase):

    TESTFN = None

    def tearDown(self):
        discard()
        if self.TESTFN is not None:
            unlink(self.TESTFN)

    @classmethod
    def tearDownClass(cls):
        if cls.TESTFN is not None:
            unlink(TESTFN)

    def test_decorate_fun(self):
        with self.assertRaises(TypeError) as cm:
            @register()
            def foo():
                pass

        self.assertIn(
            'register decorator is supposed to be used against a class',
            str(cm.exception))

    def test_translators_not_callable(self):
        self.assertRaises(TypeError, parse_with_envvars, name_translator=1)
        self.assertRaises(TypeError, parse_with_envvars, value_translator=1)

    def test_parser_with_no_file(self):
        self.assertRaises(ValueError, parse, file_parser=lambda x: {})

    def test_no_registered_class(self):
        self.assertRaises(Error, parse)

    def test_exceptions(self):
        exc = UnrecognizedKeyError(key='foo', value='bar')
        self.assertEqual(
            str(exc),
            "config file provides key 'foo' with value 'bar' but key 'foo' "
            "is not defined in the config class")
        exc = RequiredKeyError(key="foo")
        self.assertEqual(
            str(exc),
            "configuration class requires 'foo' key to be specified via "
            "config file or env var")
        exc = TypesMismatchError(key="foo", default_value=1, new_value='bar')
        self.assertEqual(
            str(exc),
            "type mismatch for key 'foo' (default_value=1) got 'bar'")

    def test_file_like(self):
        @register()
        class foo:
            foo = 1

        file = io.StringIO()
        with self.assertRaises(Error) as cm:
            parse(file)
        self.assertEqual(
            str(cm.exception),
            "can't determine format from a file object with no 'name' "
            "attribute")

        file = io.StringIO()
        parse(file, file_parser=lambda x: {})

    def test_envvar_parser_not_callable(self):
        with self.assertRaises(TypeError) as cm:
            parse_with_envvars(envvar_parser=1)
        self.assertIn("not a callable", str(cm.exception))


def main():
    verbosity = 1 if 'TOX' in os.environ else 2
    unittest.main(verbosity=verbosity)


if __name__ == '__main__':
    main()
