#! /usr/bin/env bash

git tag `python .github/fetch_version.py`  # create a new tag
git push --tags || true  # update the repository version