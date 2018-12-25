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
import os
from builtins import zip
from io import open

import datasource
import raspdata

class AbstractWaveClassifier:
    def feature(self, raspDataTimeSlice):
        raise NotImplementedError()

    def classify(self, raspDataTimeSlice):
        raise NotImplementedError()

class KCVHWaveClassifier:
    def __init__(self):
        self.weight = [0.97959826 1.05104664 1.19487818]
        self.bias = -2.49384207861
        self.threshold = 0.0

        # Allow override from environment variables
        if 'WEATHERBOT_WAVE_WEIGHT' in os.environ:
            self.weight = [float(x) for x in os.environ['WEATHERBOT_WAVE_WEIGHT'].split(':')]
        if 'WEATHERBOT_WAVE_BIAS' in os.environ:
            self.bias = float(os.environ['WEATHERBOT_WAVE_BIAS'])
        if 'WEATHERBOT_WAVE_THRESHOLD' in os.environ:
            self.threshold = float(os.environ['WEATHERBOT_WAVE_THRESHOLD'])

    def feature(self, raspDataTimeSlice):
        with raspDataTimeSlice.open('press500') as file:
            (data500mb, dims) = raspdata.parseData(file)
        with raspDataTimeSlice.open('press700') as file:
            (data700mb, _) = raspdata.parseData(file)
        with raspDataTimeSlice.open('press850') as file:
            (data850mb, _) = raspdata.parseData(file)
        with raspDataTimeSlice.open('sfcsunpct') as file:
            (dataSfcSun, _) = raspdata.parseData(file)
        # NOTE: I would rather just add a separate feature for cloud cover,
        # but right now I do not have enough data to do that. The SVM ends up
        # learning the wrong weights at the moment. So, incorporate cloud cover
        # as a modulation of the lift. Also, it is important to note that the
        # feature derived from this should be inhibitory only, because
        # being sunny does not 'help' a wave day. So, the feature should be at
        # most 0.0 on a sunny day.
        cloudCoverArea = raspdata.area(dataSfcSun, dims, lambda x: x <= 80)
        def cloudCoverFactor(x,y):
            return 1.0 - pow(cloudCoverArea, 2.0)
            #totalCloudCover = 1.0 - min(1.0, max(0.0, dataSfcSun(x, y) / 100.0))
            #return 1.0 - pow(totalCloudCover, 4.0)
        def usableLift500(x,y):
            return data500mb(x,y) * cloudCoverFactor(x,y)
        def usableLift700(x,y):
            return data700mb(x,y) * cloudCoverFactor(x,y)
        def usableLift850(x,y):
            return data850mb(x,y) * cloudCoverFactor(x,y)

        liftArea500 = raspdata.area(usableLift500, dims, lambda x: x >= 150)
        liftArea700 = raspdata.area(usableLift700, dims, lambda x: x >= 150)
        liftArea850 = raspdata.area(usableLift850, dims, lambda x: x >= 150)

        # NOTE: for numerical stability, it is important that the features be
        # roughly centered and of the same magnitude
        fMean = [0.03250895446017398, 0.037120927852635176, 0.041205600599617545]
        fStd = [0.04348280488209664, 0.049065388508064946, 0.042385589484773466]
        fRaw = [liftArea500,
                liftArea700,
                liftArea850]
                #cloudCoverArea]

        return [(x - m) / s for (x,m,s) in zip(fRaw, fMean, fStd)]

    def classify(self, raspDataTimeSlice):
        feature = self.feature(raspDataTimeSlice)
        score = raspdata.score(feature, self.weight, self.bias)
        classification = True if score >= self.threshold else False
        return classification, score

class WaveClassifierFactory:
    @staticmethod
    def __classFromName():
        return {'KCVH': KCVHWaveClassifier}
    @staticmethod
    def allClassifierNames():
        return WaveClassifierFactory.__classFromName().keys()
    @staticmethod
    def classifier(name):
        classFromName = {'KCVH': KCVHWaveClassifier}
        return WaveClassifierFactory.__classFromName()[name]()

def featuresAndLabelsFromDataset(pos, neg, classifier):
    features = []
    labels = []
    for item in pos:
        dataSource = datasource.ArchivedRASPDataSource(item[0])
        for time in item[1]:
            dataTimeSlice = datasource.ArchivedRASPDataTimeSlice(dataSource, time)
            features.append(classifier.feature(dataTimeSlice))
            labels.append(1.0)

    for item in neg:
        dataSource = datasource.ArchivedRASPDataSource(item[0])
        for time in item[1]:
            dataTimeSlice = datasource.ArchivedRASPDataTimeSlice(dataSource, time)
            features.append(classifier.feature(dataTimeSlice))
            labels.append(0.0)

    return features, labels

def evaluateDataset(pos, neg, classifier):
    nPos = sum(len(item[1]) for item in pos)
    nNeg = sum(len(item[1]) for item in neg)
    truePos = 0
    trueNeg = 0
    print('## Positives ##')
    for item in pos:
        dataSource = datasource.ArchivedRASPDataSource(item[0])
        for time in item[1]:
            dataTimeSlice = datasource.ArchivedRASPDataTimeSlice(dataSource, time)
            feature = classifier.feature(dataTimeSlice)
            _, score = classifier.classify(dataTimeSlice)
            if score >= classifier.threshold:
                truePos += 1
            print(' - {0}-{1}: {2:.3f}'.format(item[0], time, score))
            print('   Feature: {0}'.format(feature))
            print('   Score contribution: {0}'.format(['{0:.3f}'.format(x*w) for (x,w) in zip(feature, classifier.weight)]))
    print ('## Negatives ##')
    for item in neg:
        dataSource = datasource.ArchivedRASPDataSource(item[0])
        for time in item[1]:
            dataTimeSlice = datasource.ArchivedRASPDataTimeSlice(dataSource, time)
            feature = classifier.feature(dataTimeSlice)
            _, score = classifier.classify(dataTimeSlice)
            if score < classifier.threshold:
                trueNeg += 1
            print(' - {0}-{1}: {2:.3f}'.format(item[0], time, score))
            print('   Feature: {0}'.format(feature))
            print('   Score contribution: {0}'.format(['{0:.3f}'.format(x*w) for (x,w) in zip(feature, classifier.weight)]))

    falseNeg = nPos - truePos
    falsePos = nNeg - trueNeg
    precision = float(truePos) / (truePos + falsePos) if truePos > 0 else 0
    recall = float(truePos) / nPos if truePos > 0 else 0
    print('Precision: {0:.1f}%'.format(100 * precision))
    print('Recall: {0:.1f}%'.format(100* recall))

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Learn good wave days from a dataset')
    parser.add_argument('-i', '--dataset', type=str, default='data/kcvh-wave.json', metavar='path', help='Dataset json file')
    parser.add_argument('-c', '--classifier', type=str, default='KCVH', metavar='name', help='Name of the classifier')
    args = parser.parse_args()

    positives = []
    negatives = []
    with open(args.dataset) as file:
        dataset = json.load(file)
        positives = dataset['positive']
        negatives = dataset['negative']

    classifier = WaveClassifierFactory.classifier(args.classifier)
    (features, labels) = featuresAndLabelsFromDataset(positives, negatives, classifier)

    (fMin, fMax, fMean, fStd) = raspdata.featureStats(features)
    print('Feature min: {0}'.format(fMin))
    print('Feature max: {0}'.format(fMax))
    print('Feature mean: {0}'.format(fMean))
    print('Feature std: {0}'.format(fStd))

    evaluateDataset(positives, negatives, classifier)
    print('Weight: {0}'.format(classifier.weight))
    print('Bias: {0}'.format(classifier.bias))
    print('\n\n')

    (classifier.weight, classifier.bias) = raspdata.learn(features, labels)

    evaluateDataset(positives, negatives, classifier)
    print('Weight: {0}'.format(classifier.weight))
    print('Bias: {0}'.format(classifier.bias))
