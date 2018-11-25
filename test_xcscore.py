#!/usr/bin/env python

import raspdata
import xcscore

def test_classifierFactory():
    for name in xcscore.XCClassifierFactory.allClassifierNames():
        classifier = xcscore.XCClassifierFactory.classifier(name)
        assert classifier

def test_requiredData():
    for name in xcscore.XCClassifierFactory.allClassifierNames():
        classifier = xcscore.XCClassifierFactory.classifier(name)
        requiredData = classifier.requiredData()
        assert type(requiredData) == tuple
        for item in requiredData:
            assert type(item) == str

def test_feature():
    startCoordinate = (0, 0)
    endCoordinate = (1, 1)
    for name in xcscore.XCClassifierFactory.allClassifierNames():
        classifier = xcscore.XCClassifierFactory.classifier(name)
        (dims, data) = raspdata.dataFromDirectory('test-data', classifier.requiredData(), 1400)
        feature = classifier.feature(startCoordinate, endCoordinate, dims, data)
        assert type(feature) == list
        assert len(feature) == len(classifier.weight)
        for item in feature:
            assert type(item) == float

def test_score():
    startCoordinate = (0, 0)
    endCoordinate = (1, 1)
    for name in xcscore.XCClassifierFactory.allClassifierNames():
        classifier = xcscore.XCClassifierFactory.classifier(name)
        (dims, data) = raspdata.dataFromDirectory('test-data', classifier.requiredData(), 1400)
        score = classifier.score(startCoordinate, endCoordinate, dims, data)
        assert type(score) == float

def test_classify():
    startCoordinate = (0, 0)
    endCoordinate = (1, 1)
    for name in xcscore.XCClassifierFactory.allClassifierNames():
        classifier = xcscore.XCClassifierFactory.classifier(name)
        (dims, data) = raspdata.dataFromDirectory('test-data', classifier.requiredData(), 1400)
        c = classifier.classify(startCoordinate, endCoordinate, dims, data)
        assert type(c) == bool
