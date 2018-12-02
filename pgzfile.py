#!/usr/bin/env python

# This file is part of GliderWeatherBot.
#
# GliderWeatherBot is copyright Philip G. Lee, 2018.
#
# GliderWeatherBot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GliderWeatherBot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GliderWeatherBot.  If not, see <https://www.gnu.org/licenses/>.

import re
import struct
import zlib
from builtins import range, str

# NOTE: this is not technically PGM, since we are using 4 bytes per pixel
def writePgzImage(data, dims, fileStream):
    assert 'b' in fileStream.mode
    maxVal = 2**32 - 1
    fileStream.write(str('PGZ {0} {1} {2}\n'.format(dims[0], dims[1], maxVal)).encode('utf-8'))
    packedData = bytes()
    for y in range(dims[1]):
        for x in range(dims[0]):
            # Big-endian 32-bit signed integers
            packed = struct.pack('>i', data(x, y))
            packedData += packed
    fileStream.write(zlib.compress(packedData, 9))

def readPgzImage(fileStream):
    formatLine = str(fileStream.readline())
    rest = zlib.decompress(fileStream.read())

    m = re.search('PGZ (\d+) (\d+) (\d+)', formatLine)
    dims = (int(m.group(1)), int(m.group(2)))
    maxVal = int(m.group(3))

    data = []
    for y in range(dims[1]):
        rowBegin = 4 * dims[0] * y
        rowEnd = 4 * dims[0] * (y+1)
        rowStr = rest[rowBegin:rowEnd]
        dataRow = []
        for x in range(dims[0]):
            s = rowStr[(4*x):(4*(x+1))]
            dataRow.append(struct.unpack('>i', s)[0])
        data.append(dataRow)
    def ret(x,y):
        return data[y][x]
    return ret, dims
