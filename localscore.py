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

import argparse
import json
import math
import os
#import sys
from builtins import zip
from io import open

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt

import raspdata
import utilities

# NOTE: eyeballed
KCVH = (15,91)

class KCVHLocalClassifier:
    def __init__(self):
        self.weight = [1.46403088, -0.46282701, 0.75155249, -0.84861172]
        self.bias = 0.185605559061
        self.threshold = 0.0

    def imageSummary(self, raspDataTimeSlice):
        ret = '/tmp/{0}.png'.format(utilities.randomString(8))

        try:
            with raspDataTimeSlice.open('hwcrit') as file:
                (dataHcrit, dims) = raspdata.parseData(file)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            return None

        imageData = [[dataHcrit(x, y) for x in range(0, KCVH[0] + 16)] for y in reversed(range(KCVH[1] - 16, KCVH[1] + 16))]

        plt.clf()
        plt.imshow(imageData, cmap=plt.cm.get_cmap('rainbow'), vmin=0, vmax=6000, interpolation='quadric')
        plt.colorbar()
        plt.plot([KCVH[0]], [16], 'ko')
        plt.text(KCVH[0], 16-1, 'KCVH', horizontalalignment='right', color='red')
        plt.axis('off')
        plt.title('Hcrit {0}+{1} lst'.format(raspDataTimeSlice.date().isoformat(), raspDataTimeSlice.time()))
        plt.savefig(ret, bbox_inches='tight', pad_inches=0)

        return ret

    def feature(self, raspDataTimeSlice):
        gridResolution_km = 4.0

        with raspDataTimeSlice.open('hwcrit') as file:
            (dataHcrit, dims) = raspdata.parseData(file)
        with raspDataTimeSlice.open('zsfclcldif') as file:
            (cuPot, _) = raspdata.parseData(file)
        with raspDataTimeSlice.open('zsfclcl') as file:
            (cuBase, _) = raspdata.parseData(file)
        with raspDataTimeSlice.open('sfcsunpct') as file:
            (dataSfcSun, _) = raspdata.parseData(file)
        with raspDataTimeSlice.open('zblcldif') as file:
            (odPot, _) = raspdata.parseData(file)

        def roi(x, y):
            distance_km = gridResolution_km * math.sqrt( (x-KCVH[0])**2 + (y - KCVH[1])**2 )
            maxDistance_km = 8000.0 / 3281.0 * 30.0
            return 1.0 if distance_km < maxDistance_km else 0.0

        def distanceFromKCVH_km(x,y):
            return gridResolution_km * math.sqrt( (x-KCVH[0])**2 + (y - KCVH[1])**2 )

        def glideRatioFromHcrit(x,y):
            hcrit_km = dataHcrit(x,y) / 3281.0
            return distanceFromKCVH_km(x,y) / hcrit_km if roi(x,y) > 0.0 else 9999.0

        def glideRatioFromCloudbase(x,y):
            return distanceFromKCVH_km(x,y) / (cuBase(x,y) / 3281.0)

        def sunnyCuPredicate(x,y):
            cuLikelihood = 1.0 if cuPot(x,y) > 300 else 0.0
            sunny = 1.0 if dataSfcSun(x,y) > 40.0 else 0.0
            return roi(x,y) * sunny * cuLikelihood
        def sunnyCuGlideRatio(x,y):
            return sunnyCuPredicate(x,y) * glideRatioFromCloudbase(x,y)
        def sunnyCuBase(x,y):
            return sunnyCuPredicate(x,y) * cuBase(x,y)

        roiArea = raspdata.area(roi, dims, lambda x: x > 0.0)
        sunnyCuArea = sum([sunnyCuPredicate(x,y) for x in range(dims[0]) for y in range(dims[1])])
        totalOd = sum([roi(x,y) * max(0.0, odPot(x,y)) for x in range(dims[0]) for y in range(dims[1])])

        areaWhereGlideRatioIsSmall = raspdata.area(glideRatioFromHcrit, dims, lambda x: x < 30.0) / roiArea
        # NOTE: the bias below is to make the value defined when sunnyCuArea == 0
        avgSunnyCuGlideRatio = (raspdata.integral(sunnyCuGlideRatio, dims) + 2 * 60.0) / (sunnyCuArea + 2)
        # NOTE: the bias on the denominator is to penalize very small areas of sunny cu
        avgSunnyCuBase = raspdata.integral(sunnyCuBase, dims) / (sunnyCuArea + 5)

        #asdf = [[dataHcrit(x, y) for x in range(dims[0])] for y in range(dims[1])]
        #asdf = [[dataHcrit(x, y) for x in range(0, KCVH[0] + 16)] for y in reversed(range(KCVH[1] - 16, KCVH[1] + 16))]
        #asdf = [[sunnyCuBase(x, y) for x in range(dims[0])] for y in reversed(range(dims[1]))]
        #plt.imshow(asdf, cmap=plt.cm.get_cmap("rainbow"), vmin=0, vmax=7000, interpolation='quadric')
        #plt.colorbar()
        #plt.plot([KCVH[0]], [16], 'ko')
        #plt.text(KCVH[0], 16-1, 'KCVH', horizontalalignment='right', color='red')
        #plt.axis('off')
        #plt.title('Hcrit')
        #plt.savefig('/tmp/foo.png', bbox_inches='tight', pad_inches=0)
        #plt.show()

        # NOTE: totalOd is meant to shut down a good forecast, so it should have 0 'mean' here
        fRaw = [areaWhereGlideRatioIsSmall, avgSunnyCuGlideRatio, avgSunnyCuBase, totalOd]
        fMean = [0.16924182536830756, 34.73735646864805, 4607.398017239411, 0.0]
        fStd = [0.06333730851768322, 9.160819727244546, 1048.274081537685, 175856.8555367091]

        #return fRaw
        return [(x - m) / s for (x,m,s) in zip(fRaw, fMean, fStd)]

    def classify(self, raspDataTimeSlice):
        feature = self.feature(raspDataTimeSlice)
        score = raspdata.score(feature, self.weight, self.bias)
        classification = True if score >= self.threshold else False
        return classification, score

class LocalClassifierFactory:
    @staticmethod
    def __classFromName():
        return {'KCVH': KCVHLocalClassifier}
    @staticmethod
    def allClassifierNames():
        return LocalClassifierFactory.__classFromName().keys()
    @staticmethod
    def classifier(name):
        classFromName = {'KCVH': KCVHLocalClassifier}
        return LocalClassifierFactory.__classFromName()[name]()

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Learn good local days from a dataset')
    parser.add_argument('-i', '--dataset', type=str, default='data/kcvh-local.json', metavar='path', help='Dataset json file')
    parser.add_argument('-c', '--classifier', type=str, default='KCVH', metavar='name', help='Name of the classifier')
    args = parser.parse_args()

    positives = []
    negatives = []
    with open(args.dataset) as file:
        dataset = json.load(file)
        positives = dataset['positive']
        negatives = dataset['negative']

    classifier = LocalClassifierFactory.classifier(args.classifier)
    (features, labels) = raspdata.featuresAndLabelsFromDataset(positives, negatives, classifier)

    (fMin, fMax, fMean, fStd) = raspdata.featureStats(features)
    print('Feature min: {0}'.format(fMin))
    print('Feature max: {0}'.format(fMax))
    print('Feature mean: {0}'.format(fMean))
    print('Feature std: {0}'.format(fStd))

    raspdata.evaluateDataset(positives, negatives, classifier)
    print('Weight: {0}'.format(classifier.weight))
    print('Bias: {0}'.format(classifier.bias))
    print('\n\n')

    (classifier.weight, classifier.bias) = raspdata.learn(features, labels)

    raspdata.evaluateDataset(positives, negatives, classifier)
    print('Weight: {0}'.format(classifier.weight))
    print('Bias: {0}'.format(classifier.bias))
