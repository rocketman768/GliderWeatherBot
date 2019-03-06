#!/usr/bin/env python

try:
    from urllib.parse import urlparse, urlencode
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
except ImportError:
    from urlparse import urlparse
    from urllib import urlencode
    from urllib2 import urlopen, Request, HTTPError

import datetime
import os
from contextlib import closing
from io import open

import raspdata

## Abstract Classes

# Represents a 'timeless' instantaneous slice of data
class RASPDataTimeSlice:
    def time(self):
        raise NotImplementedError()
    def date(self):
        raise NotImplementedError()
    def data(self, parameter):
        raise NotImplementedError()

## RASP

class WebRASPDataSource:
    def __init__(self, baseURL):
        self.__baseURL = baseURL
        self.__parsedData = {}
    def data(self, parameter, dayOffset, time):
        dataString = '{0}-{1}-{2}'.format(parameter, dayOffset, time)
        if dataString in self.__parsedData:
            return self.__parsedData[dataString]
        else:
            url = '{0}/OUT+{1}/FCST/{2}.curr.{3}lst.d2.data'.format(
                self.__baseURL,
                dayOffset,
                parameter,
                time
            )
            with closing(urlopen(url)) as file:
                self.__parsedData[dataString] = raspdata.parseData(file)
            return self.__parsedData[dataString]

class ArchivedRASPDataSource:
    def __init__(self, directory):
        self.__directory = directory
    def data(self, parameter, time):
        filename = '{0}/{1}.curr.{2}lst.d2.data'.format(self.__directory, parameter, time)
        if not os.path.isfile(filename):
            filename = '{0}/{1}.curr.{2}lst.d2.data.pgz'.format(self.__directory, parameter, time)
        if not os.path.isfile(filename):
            raise IOError('File not found for data {0} at time {1}'.format(parameter, time))
        return raspdata.parseData(open(filename, 'rb'))

class WebRASPDataTimeSlice(RASPDataTimeSlice):
    def __init__(self, webDataSource, dayOffset, time):
        self.__webDataSource = webDataSource
        self.__dayOffset = dayOffset
        self.__time = time
        self.__today = datetime.date.today()
    def data(self, parameter):
        return self.__webDataSource.data(parameter, self.__dayOffset, self.__time)
    def time(self):
        return self.__time
    def date(self):
        return self.__today + datetime.timedelta(self.__dayOffset)

class ArchivedRASPDataTimeSlice(RASPDataTimeSlice):
    def __init__(self, archivedDataSource, time):
        self.__archivedDataSource = archivedDataSource
        self.__time = time
    def data(self, parameter):
        return self.__archivedDataSource.data(parameter, self.__time)
    def time(self):
        return self.__time
    def date(self):
        raise NotImplementedError()

## Soundings

class WebSoundingDataSource:
    def __init__(self, location):
        self.__location = location
    def openRequest(self, dataRequest, dateTime):
        model = 'GFS'
        return urlopen(rucsoundings.urlForSounding(self.__location, model, dateTime))
