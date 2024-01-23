# Shortcuts for various tasks (UNIX only).
# To use a specific Python version run:
# $ make install PYTHON=python3.3

PYTHON=python3
TSCRIPT=tests.py

INSTALL_OPTS = `$(PYTHON) -c \
	"import sys; print('' if hasattr(sys, 'real_prefix') else '--user')"`

all: test

clean:
	rm -f `find . -type f -name \*.py[co]`
	rm -f `find . -type f -name \*.so`
	rm -f `find . -type f -name .\*~`
	rm -f `find . -type f -name \*.orig`
	rm -f `find . -type f -name \*.bak`
	rm -f `find . -type f -name \*.rej`
	rm -rf `find . -type d -name __pycache__`
	rm -rf *.core
	rm -rf *.egg-info
	rm -rf *\$testfile*
	rm -rf .coverage
	rm -rf .tox
	rm -rf build
	rm -rf dist
	rm -rf docs/_build
	rm -rf htmlcov

# useful deps which are nice to have while developing / testing
setup-dev-env: install-git-hooks
	$(PYTHON) -m pip install --user --upgrade pip
	$(PYTHON) -m pip install --user --upgrade \
		coverage \
		flake8 \
		ipaddress \
		pep8 \
		pytest \
		pytest-cov \
		pyyaml \
		sphinx \
		sphinx-pypi-upload \
		toml \
		unittest2

install:
	# make sure setuptools is installed (needed for 'develop' / edit mode)
	$(PYTHON) -c "import setuptools"
	PYTHONWARNINGS=all $(PYTHON) setup.py develop $(INSTALL_OPTS)
	$(PYTHON) -c "import confix"  # make sure it actually worked


uninstall:
	cd ..; $(PYTHON) -m pip uninstall -y -v confix

test:
	$(PYTHON) -m pytest -s -v $(TSCRIPT)

# Run a specific test by name; e.g. "make test-by-name register" will run
# all test methods containing "register" in their name.
test-by-name: install
	$(PYTHON) -m pytest -s -v $(TSCRIPT) -k $(filter-out $@,$(MAKECMDGOALS))

coverage: install
	# Note: coverage options are controlled by .coveragerc file
	rm -rf .coverage htmlcov
	$(PYTHON) -m coverage run $(TSCRIPT)
	$(PYTHON) -m coverage report
	@echo "writing results to htmlcov/index.html"
	$(PYTHON) -m coverage html
	$(PYTHON) -m webbrowser -t htmlcov/confix.html

pep8:
	@git ls-files | grep \\.py$ | xargs $(PYTHON) -m pep8

pyflakes:
	@export PYFLAKES_NODOCTEST=1 && \
		git ls-files | grep \\.py$ | xargs $(PYTHON) -m pyflakes

flake8:
	@git ls-files | grep \\.py$ | xargs $(PYTHON) -m flake8

# upload source tarball on https://pypi.python.org/pypi/pysendfile.
upload-src:
	$(MAKE) clean
	PYTHONWARNINGS=all $(PYTHON) setup.py sdist
	$(PYTHON) -m twine upload dist/*.tar.gz

# Build and upload doc on https://pythonhosted.org/confix/.
# Requires "pip install sphinx-pypi-upload".
upload-doc:
	cd docs; make html
	$(PYTHON) setup.py upload_sphinx --upload-dir=docs/_build/html

# git-tag a new release
git-tag-release:
	git tag -a release-`python -c "import setup; print(setup.get_version())"` -m `git rev-list HEAD --count`:`git rev-parse --short HEAD`
	git push --follow-tags

# install GIT pre-commit hook
install-git-hooks:
	ln -sf ../../.git-pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit

todos:
	git grep -n TODO
