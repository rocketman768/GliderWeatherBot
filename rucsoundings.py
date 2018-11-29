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

def kPaFromMb(pressure_mb):
    return pressure_mb / 10.0

def degCFromK(temp_K):
    return temp_K - 273.15

def gasConstantAir():
    return 286.9

def gasConstantWaterVapor():
    return 461.4

def waterVaporPressure(temp_K):
    # This table has the actually-measured values
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
    # w = P_w / (P - P_w) * (R_a / R_w)
    return waterVaporPressure / (totalPressure - waterVaporPressure) * gasConstantAir() / gasConstantWaterVapor()

def saturationMixingRatio(totalPressure_kPa, temp_K):
    pW = waterVaporPressure(temp_K)
    return mixingRatio(totalPressure_kPa, pW)

# This is the equation for the mixing ratio lines on a skew T
def temperatureForMixingRatio(w, totalPressure_kPa):
    # w = P_w / (P - P_w) * (R_a / R_w)
    # <=>
    # P_w = [w P (R_w / R_a)] / (1 + w (R_w / R_a))
    a = w * gasConstantWaterVapor() / gasConstantAir()
    waterPressure_kPa = totalPressure_kPa * (a / (1.0 + a))
    return waterVaporTemperature(waterPressure_kPa)

# Return the standard temperature and height for the given pressure
def standardAtmosphere(pressure_kPa):
    # http://www-mdp.eng.cam.ac.uk/web/library/enginfo/aerothermal_dvd_only/aero/atmos/atmos.html
    g_ms = 9.8
    R = gasConstantAir()
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

def dryAdiabaticTemperature(pressure_kPa, surfacePressure_kPa, surfaceTemperature_K):
    g_ms = 9.8
    R = gasConstantAir()
    T0_K = surfaceTemperature_K
    L_Cm = 0.0098
    P0_kPa = surfacePressure_kPa

    # P / P0 = (T / T0)^(g/(LR))
    # (P / P0)^(LR/g) = T/T0
    # T = T0 * (P/P0)^(LR/g)
    T = T0_K * math.pow(pressure_kPa / P0_kPa, L_Cm * R / g_ms)
    return T

# Find x0 = f(x) = 0 given x0 is in [a, b]
def findRoot(f, a, b):
    assert f(a) * f(b) <= 0.0
    midpoint = 0.0
    # We should get about one bit of accuracy per iteration
    for i in range(32):
        fa = f(a)
        fb = f(b)
        midpoint = (a*fb - b*fa) / (fb - fa)
        if fa * f(midpoint) > 0.0:
            a = midpoint
        else:
            b = midpoint
    return midpoint

# NOTE: in the future, maybe parse https://forecast.weather.gov/MapClick.php?lat=36.8525&lon=-121.4033&FcstType=digitalDWML
# in order to get the maximum surface temperature during the day
def condensationLevel(surfaceTemp_K, surfaceDewpoint_K, surfacePressure_kPa):
    a_kPa = 10
    b_kPa = 150
    w = mixingRatio(surfacePressure_kPa, waterVaporPressure(surfaceDewpoint_K))
    def temperatureDifference(pressure_kPa):
        return dryAdiabaticTemperature(pressure_kPa, surfacePressure_kPa, surfaceTemp_K) - temperatureForMixingRatio(w, pressure_kPa)
    condensationLevel_kPa = findRoot(temperatureDifference, a_kPa, b_kPa)
    condensationTemp_K = temperatureForMixingRatio(w, condensationLevel_kPa)
    return condensationLevel_kPa, condensationTemp_K

if __name__=='__main__':
    # Find the condensation level if the dewpoint is -3.2C and the surface
    # temp at 1000mb is 30C
    cl_kPa, T = condensationLevel(30.0 + 273.15, -3.2 + 273.15, 100.0)
    _, hcl_m = standardAtmosphere(cl_kPa)
    print('{0} mb {1} ft {2} C'.format(cl_kPa * 10.0, hcl_m * 3.28, T - 273.15))

    #import urllib2
    #response = urllib2.urlopen(urlForSounding('KCVH', 'GFS', datetime.datetime(2018,11,26,21,0,0)))
    #sounding, surfaceNdx = parseSounding(response)
    #print(sounding)
    #print(surfaceNdx)
