#!/usr/bin/env python

import datasource
import raspdata
import xcscore

def test_classifierFactory():
    for name in xcscore.XCClassifierFactory.allClassifierNames():
        classifier = xcscore.XCClassifierFactory.classifier(name)
        assert classifier

def test_feature():
    dataSlice = datasource.ArchivedRASPDataTimeSlice(
        datasource.ArchivedRASPDataSource('test-data'),
        1400
    )
    startCoordinate = (0, 0)
    endCoordinate = (1, 1)
    for name in xcscore.XCClassifierFactory.allClassifierNames():
        classifier = xcscore.XCClassifierFactory.classifier(name)
        feature = classifier.feature(startCoordinate, endCoordinate, dataSlice)
        assert type(feature) == list
        assert len(feature) == len(classifier.weight)
        for item in feature:
            assert type(item) == float

def test_classify():
    dataSlice = datasource.ArchivedRASPDataTimeSlice(
        datasource.ArchivedRASPDataSource('test-data'),
        1400
    )
    startCoordinate = (0, 0)
    endCoordinate = (1, 1)
    for name in xcscore.XCClassifierFactory.allClassifierNames():
        classifier = xcscore.XCClassifierFactory.classifier(name)
        c, score = classifier.classify(startCoordinate, endCoordinate, dataSlice)
        assert type(c) == bool
        assert type(score) == float
