# Shortcuts for various tasks (UNIX only).
# To use a specific Python version run:
# $ make install PYTHON=python3.3

.PHONY: install uninstall test pep8 pyflakes clean upload-src

PYTHON=python
TSCRIPT=tests.py
FLAGS=

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
	rm -rf .tox
	rm -rf build
	rm -rf dist
	rm -rf docs/_build

install:
	$(PYTHON) setup.py install --user

install-deps:
	$(PYTHON) -m pip install --upgrade --user PyYAML toml

uninstall:
	cd ..; $(PYTHON) -m pip uninstall -y -v confix

test: install
	$(PYTHON) $(TSCRIPT)

# requires "pip install pep8"
pep8:
	@git ls-files | grep \\.py$ | xargs $(PYTHON) -m pep8

# requires "pip install pyflakes"
pyflakes:
	@export PYFLAKES_NODOCTEST=1 && \
		git ls-files | grep \\.py$ | xargs $(PYTHON) -m pyflakes

# requires "pip install flake8"
flake8:
	@git ls-files | grep \\.py$ | xargs $(PYTHON) -m flake8

# upload source tarball on https://pypi.python.org/pypi/pysendfile.
upload-src: clean
	$(PYTHON) setup.py sdist upload

# git-tag a new release
git-tag-release:
	git tag -a release-`python -c "import setup; print(setup.get_version())"` -m `git rev-list HEAD --count`:`git rev-parse --short HEAD`
	echo "done; now run 'git push --follow-tags' to push the new tag on the remote repo"

# install GIT pre-commit hook
install-git-hooks:
	ln -sf ../../.git-pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
