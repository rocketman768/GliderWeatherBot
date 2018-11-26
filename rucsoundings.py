#!/usr/bin/env python

import datetime
import re

# Get the URL for the text sounding
# location can be an airport like 'KCVH' or '<lat>,<long>' in decimal format
def urlForSounding(location, model, dateTime):
    if model not in ('Op40', 'Bak40', 'Bak13', 'FIM', 'GFS', 'NAM', 'RAOB'):
        raise ValueError('{0} is not a valid model')
    epoch = datetime.datetime.utcfromtimestamp(0)
    timeStart = (dateTime - epoch).total_seconds()
    timeEnd = timeStart + 3600
    url = 'https://rucsoundings.noaa.gov/get_soundings.cgi?data_source={0}&startSecs={1}&endSecs={2}&fcst_len=shortest&airport={3}'.format(model, timeStart, timeEnd,location)
    return url

def parseSounding(file):
    # https://rucsoundings.noaa.gov/raob_format.html
    # First six lines are informational
    for x in range(6):
        file.readline()

    ret = []
    surfaceNdx = -1
    while True:
        line = file.readline()
        if not line or line.isspace():
            break
        m = re.search('^\s+(\d)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)', line)
        type = int(m.group(1))
        mbTenths = int(m.group(2))
        pAltMeters = int(m.group(3))
        tempCTenths = int(m.group(4))
        dewpointCTenths = int(m.group(5))
        windDirDeg = int(m.group(6))
        windSpeedKt = int(m.group(7))

        if type == 9:
            surfaceNdx = len(ret)
        ret.append((float(mbTenths) / 10.0, float(pAltMeters), float(tempCTenths) / 10.0, float(dewpointCTenths) / 10.0, float(windDirDeg), float(windSpeedKt)))

    return ret, surfaceNdx

if __name__=='__main__':
    import urllib2
    response = urllib2.urlopen(urlForSounding('KCVH', 'GFS', datetime.datetime(2018,11,26,21,0,0)))
    sounding, surfaceNdx = parseSounding(response)
    print(sounding)
    print(surfaceNdx)
