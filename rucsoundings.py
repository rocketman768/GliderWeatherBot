#!/usr/bin/env python

import datetime
import math
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

def kPaFromMb(pressure_mb):
    return pressure_mb / 10.0

def degCFromK(temp_K):
    return temp_K - 273.15

def gasConstantAir():
    return 286.9

def gasConstantWaterVapor():
    return 461.4

def waterVaporPressure(temp_K):
    # T(C) | P(kPa)
    #+++++++++++++++
    #    0 | 0.61121
    #   20 | 2.3388
    #   35 | 5.6267
    #   50 | 12.344
    #   75 | 38.563
    #  100 | 101.32

    # Buck equation
    k = 0.61121
    a = 18.678
    b = 234.5
    c = 257.14
    temp_C = degCFromK(temp_K)
    return k * math.exp((a - temp_C / b) * (temp_C / (c + temp_C)))

def waterVaporTemperature(waterPressure_kPa):
    # Inverse of Buck equation
    k = 0.61121
    a = 18.678
    b = 234.5
    c = 257.14

    A = -1.0
    B = (a*b - b * math.log(waterPressure_kPa / k))
    C = -b * c * math.log(waterPressure_kPa / k)
    T0 = (-B + math.sqrt(B*B - 4 * A * C)) / (2.0 * A)
    #T1 = (-B - math.sqrt(B*B - 4 * A * C)) / (2.0 * A)
    return T0 + 273.15

def mixingRatio(totalPressure, waterVaporPressure):
    return waterVaporPressure / (totalPressure - waterVaporPressure) * gasConstantWaterVapor() / gasConstantAir()

def saturationMixingRatio(totalPressure_kPa, temp_K):
    pW = waterVaporPressure(temp_K)
    return mixingRatio(totalPressure_kPa, pW)

def temperatureForMixingRatio(w, totalPressure_kPa):
    return 0.0

# Return the standard temperature and height for the given pressure
def standardAtmosphere(pressure_kPa):
    # http://www-mdp.eng.cam.ac.uk/web/library/enginfo/aerothermal_dvd_only/aero/atmos/atmos.html
    g_ms = 9.8
    R = 287.0
    T0_K = 19.0 + 273.15
    h0_m = -610.0
    #L_Cm = 0.0065
    L_Cm = (55.0 + 19.0) / (11000.0 + 610.0)
    P0_kPa = 108.9

    # Tropopause
    Ts = -55.0 + 273.15
    Ps = 22.632
    hs = h0_m + (T0_K - Ts) / L_Cm # == 11.000km

    # P / P0 = (T / T0)^(g/(LR))
    # (P / P0)^(LR/g) = T/T0
    # T = T0 * (P/P0)^(LR/g)
    T = T0_K * math.pow(pressure_kPa / P0_kPa, L_Cm * R / g_ms)
    if T >= Ts:
        h = h0_m + (T0_K - T) / L_Cm
    else:
        # log(P/Ps) = g (hs - h) / (R Ts)
        # (R Ts / g) log(P/Ps) = hs - h
        T = Ts
        h = hs - (R * Ts / g_ms) * math.log(pressure_kPa / Ps)

    return T, h

if __name__=='__main__':
    print(waterVaporPressure(273.15))
    print(waterVaporTemperature(0.61121))
    print(waterVaporTemperature(2.3388))
    #for P_mb in (1000, 850, 750, 700, 228, 200, 150):
    #    T, h = standardAtmosphere(kPaFromMb(P_mb))
    #    print('P: {0} T: {1} h: {2}'.format(P_mb, (T - 273.15), h*3.28))

    #import urllib2
    #response = urllib2.urlopen(urlForSounding('KCVH', 'GFS', datetime.datetime(2018,11,26,21,0,0)))
    #sounding, surfaceNdx = parseSounding(response)
    #print(sounding)
    #print(surfaceNdx)
