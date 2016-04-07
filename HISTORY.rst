Bug tracker at https://github.com/giampaolo/confix/issues

Version 0.2.2 - XXXX-XX-XX
==========================

- #18: isurl() validator.
- #19: isip4(), isip6() and isip46() validators.
- #XXX: schema() has a new 'type_check' parameter.

Version 0.2.1 - 2015-07-28
==========================

- rename exceptions

Version 0.2.0 - 2015-07-28
==========================

- #2: added tox support to ease up testing on multiple python versions
- #3: optional conf_file parameter
- #6: allow section-less conf files (also temporarily remove support for .ini
  files)
- #7: parse also env vars (parse_with_envvars()).
- #8: debug logging.
- #9: rst doc: http://pythonhosted.org/confix
- #10: istrue, isin, isnotin, isemail validators
- #11: chained validators
- #12: @register-ed class is dict()able (patch by Josiah Carlson).
- #13: get_parsed_conf() function
- #14: version_info tuple
- #16: be thread safe
- #17: continuous test integration for Windows.

Version 0.1.0 - 2014-02-22
==========================

- Initial version
