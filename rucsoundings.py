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
        ret.append({
            'pressure':       float(mbTenths) / 10.0,
            'altitude':       float(pAltMeters),
            'temperature':    float(tempCTenths) / 10.0,
            'dewpoint':       float(dewpointCTenths) / 10.0,
            'wind-direction': float(windDirDeg),
            'wind-speed':     float(windSpeedKt)
        })

    return ret, surfaceNdx

def interpolateSounding(sounding, altitude):
    def shortestAngle(a0, a1):
        da = (a1 - a0) % 360.0
        return 2.0 * da % 360.0 - da

    ret = {}
    for i in range(len(sounding)):
        alt = sounding[i]['altitude']
        if alt > altitude:
            if i > 0:
                lastAlt = sounding[i-1]['altitude']
                pct = (altitude - lastAlt) / (alt - lastAlt)
                for key in sounding[i].keys():
                    value = sounding[i][key]
                    lastValue = sounding[i-1][key]
                    if key == 'wind-direction':
                        ret[key] = lastValue + pct * shortestAngle(lastValue, value)
                    else:
                        ret[key] = lastValue + pct * (value - lastValue)
            else:
                ret = sounding[i]
            break
    return ret

def freezingLevel(sounding):
    for i in range(len(sounding)):
        temp = sounding[i]['temperature']
        if temp < 0:
            if i > 0:
                lastTemp = sounding[i-1]['temperature']
                pct = (0.0 - lastTemp) / (temp - lastTemp)
                pAlt = sounding[i]['altitude']
                lastPAlt = sounding[i-1]['altitude']
                return pct * (pAlt - lastPAlt) + lastPAlt
            else:
                return temp
    return None

# NOTE: in the future, maybe parse https://forecast.weather.gov/MapClick.php?lat=36.8525&lon=-121.4033&FcstType=digitalDWML
# in order to get the maximum surface temperature during the day
def condenstationLevel(sounding, surfaceNdx, surfaceTemp_C):
    # These SHOULD be 9.8 deg/km and 2.0 deg/km respectively, but that
    # does not line up with the 2.5 deg/1000ft combined lapse rate that
    # us pilots are taught. That would be 8.2 deg/km.
    dryAdiabaticLapseRate_degCPerM = 10.0 / 1000.0
    dewpointLapseRate_degCPerM = 1.8 / 1000.0
    surfaceDewpoint_C = sounding[surfaceNdx]['dewpoint']
    return sounding[surfaceNdx]['altitude'] + (surfaceTemp_C - surfaceDewpoint_C) / (dryAdiabaticLapseRate_degCPerM - dewpointLapseRate_degCPerM)

if __name__=='__main__':
    import urllib2
    response = urllib2.urlopen(urlForSounding('KCVH', 'GFS', datetime.datetime(2018,11,26,21,0,0)))
    sounding, surfaceNdx = parseSounding(response)
    print(sounding)
    print(surfaceNdx)
