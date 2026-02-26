#!/bin/bash
# Wrapper to run the new TAXSIM Linux binary via Docker
cat | docker run --platform linux/amd64 --rm -i \
  -v /Users/pavelmakarchuk/policyengine-taxsim/resources/taxsimtest/taxsimtest-osx-new.exe:/taxsim:ro \
  ubuntu:24.04 /taxsim
