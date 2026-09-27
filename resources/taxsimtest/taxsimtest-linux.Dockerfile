# Runtime image for taxsimtest-linux.exe, used by taxsim-docker-wrapper.sh.
#
# The binary is a dynamically linked gfortran ELF (x86-64) that needs
# libgfortran.so.5 and libquadmath.so.0, which plain ubuntu:24.04 and
# debian:stable-slim lack ("libgfortran.so.5: cannot open shared object
# file", exit 127). The binary itself is bind-mounted at run time rather than
# copied in, so refreshing it never requires rebuilding this image.
#
# The wrapper builds it on first use, tagged policyengine-taxsim-linux:<hash of
# this file>. To use it without the wrapper, build it by hand (linux/amd64: the
# binary is x86-64 only; no build context is needed):
#   docker build --platform linux/amd64 -t policyengine-taxsim-linux - < taxsimtest-linux.Dockerfile
FROM ubuntu:24.04
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgfortran5 libquadmath0 \
    && rm -rf /var/lib/apt/lists/*
