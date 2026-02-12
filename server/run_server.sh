#!/bin/bash
source /etc/profile.d/pynq_venv.sh
source /etc/profile.d/xrt_setup.sh

/usr/local/share/pynq-venv/bin/python pynq_scope_server.py "$@"