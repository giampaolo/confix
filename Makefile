# Shortcuts for various tasks (UNIX only).
# To use a specific Python version run:
# $ make install PYTHON=python3.3

PYTHON=python3
TSCRIPT=tests.py
INSTALL_OPTS = `$(PYTHON) -c \
	"import sys; print('' if hasattr(sys, 'real_prefix') else '--user')"`

# if make is invoked with no arg, default to `make help`
.DEFAULT_GOAL := help

# ===================================================================
# Install
# ===================================================================

clean:  ## Remove all build files.
	@rm -rfv `find . \
		-type d -name __pycache__ \
		-o -type f -name \*.bak \
		-o -type f -name \*.orig \
		-o -type f -name \*.pyc \
		-o -type f -name \*.pyd \
		-o -type f -name \*.pyo \
		-o -type f -name \*.rej \
		-o -type f -name \*.so \
		-o -type f -name \*.~ \
		-o -type f -name \*\$testfn`
	@rm -rfv \
		*.core \
		*.egg-info \
		*\@psutil-* \
		.coverage \
		.failed-tests.txt \
		.pytest_cache \
		.ruff_cache/ \
		build/ \
		dist/ \
		docs/_build/ \
		htmlcov/ \
		wheelhouse

setup-dev-env:  # useful deps which are nice to have while developing / testing
	${MAKE} install-git-hooks
	$(PYTHON) -m pip install --user --upgrade pip
	$(PYTHON) -m pip install --user --upgrade \
		coverage \
		pytest \
		pyyaml \
		sphinx \
		sphinx-pypi-upload \
		toml

install:
	# make sure setuptools is installed (needed for 'develop' / edit mode)
	$(PYTHON) -c "import setuptools"
	PYTHONWARNINGS=all $(PYTHON) setup.py develop $(INSTALL_OPTS)
	$(PYTHON) -c "import confix"  # make sure it actually worked

uninstall:
	cd ..; $(PYTHON) -m pip uninstall -y -v confix

# ===================================================================
# Tests
# ===================================================================

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

# ===================================================================
# Linters
# ===================================================================

ruff:  ## Run ruff linter.
	@git ls-files '*.py' | xargs $(PYTHON) -m ruff check --no-cache
	@git ls-files '*.py' | xargs $(PYTHON) -m ruff format --check

fix-ruff:
	@git ls-files '*.py' | xargs $(PYTHON) -m ruff --no-cache --fix
	@git ls-files '*.py' | xargs $(PYTHON) -m ruff format --no-cache

# ===================================================================
# Distribution
# ===================================================================

sdist:  ## Create tar.gz source distribution.
	$(MAKE) clean
	PYTHONWARNINGS=all $(PYTHON) setup.py sdist

release:  # Upload source tarball on https://pypi.python.org/pypi/pysendfile.
	$(MAKE) sdist
	$(PYTHON) -m twine upload dist/*.tar.gz
	$(MAKE) git-tag-release

# Build and upload doc on https://pythonhosted.org/confix/.
# Requires "pip install sphinx-pypi-upload".
upload-doc:
	cd docs; make html
	$(PYTHON) setup.py upload_sphinx --upload-dir=docs/_build/html

# git-tag a new release
git-tag-release:
	git tag -a release-`python -c "import setup; print(setup.get_version())"` -m `git rev-list HEAD --count`:`git rev-parse --short HEAD`
	git push --follow-tags

# ===================================================================
# Misc
# ===================================================================

# install GIT pre-commit hook
install-git-hooks:
	ln -sf ../../.git-pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit

todos:
	git grep -n TODO
