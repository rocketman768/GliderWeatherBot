#!/usr/bin/env python

import subprocess

def test_download():
    subprocess.check_call(['./download-rasp.py', '--binary', '--output=/tmp/'])
    subprocess.call(['rm', '/tmp/*.pgz'])
