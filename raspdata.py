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

try:
    import sklearn.svm
except ImportError:
    # Learning will be disabled
    pass

import itertools
import math
import os
from builtins import range, str, zip
from io import open

import pgzfile

def rectDomain(dims):
    def listProduct(listOfIterables):
        return itertools.product(*listOfIterables)
    return listProduct(range(x) for x in dims)

def isValueValid(val):
    return val > -999999 and val < 999999

def at(u, image):
    return image(u[0], u[1])

def minMax(image, dims):
    validValues = [at(coord, image) for coord in rectDomain(dims) if isValueValid(at(coord, image))]
    retMin = min(validValues)
    retMax = max(validValues)
    return retMin, retMax

def area(image, dims, predicate):
    validValues = [at(coord, image) for coord in rectDomain(dims) if isValueValid(at(coord, image))]
    total = len(validValues)
    totalPredicate = sum([1 if predicate(x) else 0 for x in validValues])
    return float(totalPredicate) / total

# Parse the data into image, (width, height)
def parseData(fileStream):
    data = [];

    # First line is garbage (unless this is a PGZ image)
    firstLine = str(fileStream.readline())
    if 'PGZ' in firstLine:
        fileStream.seek(0)
        return pgzfile.readPgzImage(fileStream)
    # Title is next
    title = fileStream.readline()
    params1 = fileStream.readline()
    params2 = fileStream.readline()

    line = fileStream.readline().decode('ascii')
    while line:
        row = [int(x) for x in line.split(' ')]
        data.append(row)
        line = fileStream.readline().decode('ascii')

    height = len(data)
    width = len(data[0])
    def image(x,y):
        if x >= 0 and x < width and y >=0 and y < height:
            return data[y][x]
        else:
            raise ValueError('({0}, {1}) not in (0..{2}, 0..{3})'.format(x,y,width-1,height-1))
    return image, (width, height)

def featureStats(features):
    N = len(features)
    fLen = len(features[0])
    fMin = [1e6 for x in range(fLen)]
    fMax = [-1e6 for x in range(fLen)]
    fMean = [0 for x in range(fLen)]
    fStd = [0 for x in range(fLen)]

    for feature in features:
        for f in range(fLen):
            fMin[f] = min(fMin[f], feature[f])
            fMax[f] = max(fMax[f], feature[f])
            fMean[f] += feature[f]
    fMean = [float(x) / N for x in fMean]
    for feature in features:
        for f in range(fLen):
            fStd[f] += pow(float(feature[f]) - fMean[f], 2.0)
    fStd = [math.sqrt(x / N) for x in fStd]
    return fMin, fMax, fMean, fStd

# -- Learning --
def score(feature, weight, bias=0):
    if len(feature) != len(weight):
        raise ValueError('Feature (size={0}) and weight (size={1}) have unequal sizes'.format(len(feature), len(weight)))
    return sum([f * w for (f, w) in zip(feature, weight)]) + bias

def loss(features, labels, weight):
    N = len(features)

    ret = 0.0
    for (feature, label) in zip(features, labels):
        s = score(feature, weight)
        ret += (label - s) * (label - s)

    return ret / N

def lossGradient(features, labels, weight):
    N = len(features)

    ret = [0.0 for x in weight]
    for (feature, label) in zip(features, labels):
        s = score(feature, weight)
        ret = [r + 2.0 * (s - label) * f for (r,f) in zip(ret, feature)]

    return [r / N for r in ret]

#def learn(features, labels, weight, learningRate):
    #thisLoss = 0
    #lastLoss = 1
    ## Gradient descent
    #for iteration in range(1000):
    #    thisLoss = loss(features, labels, weight)
    #    if thisLoss > lastLoss:
    #        print('Learning became unstable at iteration {0}. Try smaller learning rate.'.format(iteration))
    #        break
    #    weight = [w - learningRate*g for (w,g) in zip(weight, lossGradient(features, labels, weight))]
    #    lastLoss = thisLoss
    #return weight, lastLoss
def learn(features, labels):
    classifier = sklearn.svm.SVC(kernel='linear', verbose=True)
    classifier.fit(features, labels)
    weight = classifier.coef_[0]
    bias = classifier.intercept_[0]
    return weight, bias
