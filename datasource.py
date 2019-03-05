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

## Abstract Classes

# Represents a 'timeless' instantaneous slice of data
class RASPDataTimeSlice:
    def time(self):
        raise NotImplementedError()
    def date(self):
        raise NotImplementedError()
    def open(self, parameter):
        raise NotImplementedError()

## RASP

class WebRASPDataSource:
    def __init__(self, baseURL):
        self.__baseURL = baseURL
    def open(self, parameter, dayOffset, time):
        url = '{0}/OUT+{1}/FCST/{2}.curr.{3}lst.d2.data'.format(
            self.__baseURL,
            dayOffset,
            parameter,
            time
        )
        return closing(urlopen(url))

class ArchivedRASPDataSource:
    def __init__(self, directory):
        self.__directory = directory
    def open(self, parameter, time):
        filename = '{0}/{1}.curr.{2}lst.d2.data'.format(self.__directory, parameter, time)
        if not os.path.isfile(filename):
            filename = '{0}/{1}.curr.{2}lst.d2.data.pgz'.format(self.__directory, parameter, time)
        if not os.path.isfile(filename):
            raise IOError('File not found for data {0} at time {1}'.format(parameter, time))
        return open(filename, 'rb')

class WebRASPDataTimeSlice(RASPDataTimeSlice):
    def __init__(self, webDataSource, dayOffset, time):
        self.__webDataSource = webDataSource
        self.__dayOffset = dayOffset
        self.__time = time
        self.__today = datetime.date.today()
    def open(self, parameter):
        return self.__webDataSource.open(parameter, self.__dayOffset, self.__time)
    def time(self):
        return self.__time
    def date(self):
        return self.__today + datetime.timedelta(self.__dayOffset)

class ArchivedRASPDataTimeSlice(RASPDataTimeSlice):
    def __init__(self, archivedDataSource, time):
        self.__archivedDataSource = archivedDataSource
        self.__time = time
    def open(self, parameter):
        return self.__archivedDataSource.open(parameter, self.__time)
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
