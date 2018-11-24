#!/usr/bin/env python

import pgzfile

def test_pgzfile():
    dims = (110, 130)
    def data(x,y):
        return int(x)*int(y)
    with open('/tmp/image.pgz', 'w') as file:
        pgzfile.writePgzImage(data, dims, file)
    with open('/tmp/image.pgz', 'r') as file:
        (testData, testDims) = pgzfile.readPgzImage(file)
        assert dims == testDims
        for y in range(dims[1]):
            for x in range(dims[0]):
                assert data(x, y) == testData(x, y)
