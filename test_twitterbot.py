#!/usr/bin/env python

import subprocess

import twitterbot

def test_placeholder():
    assert True

def test_help():
    subprocess.check_call(['./twitterbot.py', '--help'])

def test_run():
    subprocess.check_call(['./twitterbot.py', '--dry-run', '--wave-lookahead=1', '--xc-lookahead=1'])
