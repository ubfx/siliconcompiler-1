#!/bin/bash

# Trick to get this script's directory so that we can run
# this file from project root.
# https://stackoverflow.com/a/246128
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

sc -design gcd \
   $SCRIPT_DIR/gcd.v \
   $SCRIPT_DIR/gcd_asap7.sdc \
   -constraint_density 30 \
   -target "asap7_demo" \
   -loglevel "INFO" \
   -novercheck \
   -quiet \
   -relax \
   -track \
   -clean
