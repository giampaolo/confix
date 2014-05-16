# TODO:
# -test parse()'s 'format' parameter

import errno
import json
import os
import sys
import textwrap
try:
    import configparser  # py3
except ImportError:
    import ConfigParser as configparser

if sys.version_info >= (2, 7):
    import unittest
else:
    import unittest2 as unittest  # https://pypi.python.org/pypi/unittest2

try:
    import toml
except ImportError:
    toml = None
try:
    import yaml
except ImportError:
    yaml = None

from confix import register, parse, discard, schema
from confix import Error, InvalidKeyError, TypesMismatchError, RequiredKeyError
from confix import ValidationError


THIS_MODULE = os.path.splitext(os.path.basename(__file__))[0]
TESTFN = '$testfile'
PY3 = sys.version_info >= (3, )

if PY3:
    import io
    StringIO = io.StringIO
else:
    from StringIO import StringIO


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

    def dict_to_file(self, dct):
        raise NotImplementedError('must be implemented in subclass')

    def write_to_file(self, content, fname=None):
        if fname is None:
            fname = self.TESTFN
        with open(fname, 'w') as f:
            f.write(content)

    def test_empty_conf_file(self):
        @register('name')
        class config:
            foo = 1
            bar = 2
        self.write_to_file("   ")
        parse(self.TESTFN)
        self.assertEqual(config.foo, 1)
        self.assertEqual(config.bar, 2)

    def test_unknown_format(self):
        with open(TESTFN, 'w') as f:
            f.write('foo')
        self.addCleanup(unlink, TESTFN)
        self.assertRaises(ValueError, parse, TESTFN)

    def test_conf_file_overrides_one(self):
        @register('name')
        class config:
            foo = 1
            bar = 2
        self.dict_to_file({
            'name': dict(foo=5)
        })
        parse(self.TESTFN)
        self.assertEqual(config.foo, 5)
        self.assertEqual(config.bar, 2)

    def test_conf_file_overrides_both(self):
        @register('name')
        class config:
            foo = 1
            bar = 2
        self.dict_to_file({
            'name': dict(foo=5, bar=6)
        })
        parse(self.TESTFN)
        self.assertEqual(config.foo, 5)
        self.assertEqual(config.bar, 6)

    def test_invalid_field(self):
        @register('name')
        class config:
            foo = 1
            bar = 2
        self.dict_to_file({
            'name': dict(foo=5, apple=6)
        })
        with self.assertRaises(InvalidKeyError) as cm:
            parse(self.TESTFN)
        self.assertEqual(cm.exception.section, 'name')
        self.assertEqual(cm.exception.key, 'apple')

    # TODO: make this reliable across different languages
    # def test_types_mismatch(self):
    #     @register('name')#
    #     class config:
    #         foo = 1
    #         bar = 2
    #     self.dict_to_file({
    #         THIS_MODULE: dict(foo=5, bar='6')
    #     })

    #     with self.assertRaises(TypesMismatchError) as cm:
    #         parse(self.TESTFN)
    #     self.assertEqual(cm.exception.section, 'name')
    #     self.assertEqual(cm.exception.key, 'bar')
    #     self.assertEqual(cm.exception.default_value, 2)
    #     self.assertEqual(cm.exception.new_value, '6')

    # def test_invalid_yaml_file(self):
    #     self.dict_to_file('?!?')
    #     with self.assertRaises(Error) as cm:
    #         parse(self.TESTFN)

    def test_already_configured(self):
        @register('name')
        class config:
            foo = 1
            bar = 2
        self.dict_to_file({
            'name': dict(foo=5, bar=6)
        })
        parse(self.TESTFN)
        self.assertRaises(Error, parse, self.TESTFN)

    def test_schema_base(self):
        @register('name')
        class config:
            foo = schema(10)
        self.dict_to_file({})
        parse(self.TESTFN)
        self.assertEqual(config.foo, 10)

    def test_schema_base_required(self):
        @register('name')
        class config:
            foo = schema(10, required=True)
            bar = 2
        self.dict_to_file({
            'name': dict(bar=2)
        })
        with self.assertRaises(RequiredKeyError) as cm:
            parse(self.TESTFN)
        self.assertEqual(cm.exception.section, 'name')
        self.assertEqual(cm.exception.key, 'foo')

    def test_schema_base_overwritten(self):
        @register('name')
        class config:
            foo = schema(10, required=True)
        self.dict_to_file({
            'name': dict(foo=5)
        })
        parse(self.TESTFN)
        self.assertEqual(config.foo, 5)

    def test_schema_errors(self):
        # no default nor required=True
        self.assertRaises(TypeError, schema)
        # not callable validator
        self.assertRaises(ValueError, schema, 10, False, 'foo')

    def test_validator_ok(self):
        @register('name')
        class config:
            foo = schema(10, validator=lambda x: isinstance(x, int))
        self.dict_to_file({
            'name': dict(foo=5)
        })
        parse(self.TESTFN)

    def test_validator_ko(self):
        @register('name')
        class config:
            foo = schema(10, validator=lambda x: isinstance(x, str))
        self.dict_to_file({
            'name': dict(foo=5)
        })
        with self.assertRaises(ValidationError) as cm:
            parse(self.TESTFN)
        self.assertEqual(cm.exception.section, 'name')
        self.assertEqual(cm.exception.key, 'foo')
        self.assertEqual(cm.exception.value, 5)

    def test_validator_ko_custom_exc_w_message(self):
        def validator(value):
            raise ValidationError('message')

        @register('name')
        class config:
            foo = schema(10, validator=validator)
        self.dict_to_file({
            'name': dict(foo=5)
        })
        with self.assertRaises(ValidationError) as cm:
            parse(self.TESTFN)
        self.assertEqual(cm.exception.section, 'name')
        self.assertEqual(cm.exception.key, 'foo')
        self.assertEqual(cm.exception.value, 5)
        self.assertEqual(cm.exception.msg, 'message')

    def test_validator_ko_custom_exc_w_no_message(self):
        def validator(value):
            raise ValidationError

        @register('name')
        class config:
            foo = schema(10, validator=validator)
        self.dict_to_file({
            'name': dict(foo=5)
        })
        with self.assertRaises(ValidationError) as cm:
            parse(self.TESTFN)
        self.assertEqual(cm.exception.section, 'name')
        self.assertEqual(cm.exception.key, 'foo')
        self.assertEqual(cm.exception.value, 5)
        self.assertEqual(cm.exception.msg, None)
        self.assertIn('(got 5)', str(cm.exception))


# ===================================================================
# mixin tests
# ===================================================================

class TestJsonMixin(TestBase, unittest.TestCase):
    TESTFN = TESTFN + 'testfile.json'

    def dict_to_file(self, dct):
        self.write_to_file(json.dumps(dct))


class TestIniMixin(TestBase, unittest.TestCase):
    TESTFN = TESTFN + 'testfile.ini'

    def dict_to_file(self, dct):
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


@unittest.skipUnless(toml is not None, "toml module is not installed")
class TestTomlMixin(TestBase, unittest.TestCase):
    TESTFN = TESTFN + 'testfile.toml'

    def dict_to_file(self, dct):
        # TODO: make this more reliable
        content = ""
        for section, values in dct.items():
            content += "[%s]\n" % section
            for key, value in values.items():
                content += "%s = %s\n" % (key, value)
        self.write_to_file(content)


@unittest.skipUnless(yaml is not None, "yaml module is not installed")
class TestYamlMixin(TestBase, unittest.TestCase):
    TESTFN = 'testfile.yaml'

    def dict_to_file(self, dct):
        content = ""
        for section, values in dct.items():
            content += "%s:\n" % section
            for key, value in values.items():
                content += "    %s: %r\n" % (key, value)
        self.write_to_file(content)


# ===================================================================
# tests for a specific format
# ===================================================================

class TestIni(unittest.TestCase):
    TESTFN = TESTFN + '.ini'

    def tearDown(self):
        discard()
        unlink(self.TESTFN)

    def write_to_file(self, content):
        with open(self.TESTFN, 'w') as f:
            f.write(content)

    # XXX: should this test be common to all formats?
    def test_int_ok(self):
        @register('name')
        class config:
            foo = 1
            bar = 2
        self.write_to_file(textwrap.dedent("""
            [name]
            foo = 9
        """))
        parse(self.TESTFN)
        self.assertEqual(config.foo, 9)

    # XXX: should this test be common to all formats?
    def test_int_ko(self):
        @register('name')
        class config:
            foo = 1
            bar = 2
        self.write_to_file(textwrap.dedent("""
            [name]
            foo = '9'
        """))
        self.assertRaises(TypesMismatchError, parse, self.TESTFN)

    def test_float(self):
        @register('name')
        class config:
            foo = 1.1
            bar = 2
        self.write_to_file(textwrap.dedent("""
            [name]
            foo = 1.3
        """))
        parse(self.TESTFN)
        self.assertEqual(config.foo, 1.3)

    def test_true(self):
        @register('name')
        class config:
            foo = None
            bar = 2
        true_values = ("1", "yes", "true", "on")
        for value in true_values:
            self.write_to_file(textwrap.dedent("""
                [name]
                foo = %s
            """ % (value)))
            parse(self.TESTFN)
            self.assertEqual(config.foo, True)
            discard()

    def test_false(self):
        @register('name')
        class config:
            foo = None
            bar = 2
        true_values = ("0", "no", "false", "off")
        for value in true_values:
            self.write_to_file(textwrap.dedent("""
                [name]
                foo = %s
            """ % (value)))
            parse(self.TESTFN)
            self.assertEqual(config.foo, False)
            discard()


def test_main():
    unittest.main(verbosity=2)

if __name__ == '__main__':
    test_main()
