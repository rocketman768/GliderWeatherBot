#!/usr/bin/env python

import subprocess
from builtins import range
from io import open

import pgzfile

def test_pgzfile():
    dims = (110, 130)
    def data(x,y):
        return int(x)*int(y)
    with open('/tmp/image.pgz', 'wb') as file:
        pgzfile.writePgzImage(data, dims, file)
    with open('/tmp/image.pgz', 'rb') as file:
        (testData, testDims) = pgzfile.readPgzImage(file)
        assert dims == testDims
        for y in range(dims[1]):
            for x in range(dims[0]):
                assert data(x, y) == testData(x, y)

def test_help():
    subprocess.check_call(['./pgzfile.py', '--help'])
