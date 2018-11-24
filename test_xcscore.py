#!/usr/bin/env python

import xcscore

def test_classifierFactory():
    for name in xcscore.XCClassifierFactory.allClassifierNames():
        classifier = xcscore.XCClassifierFactory.classifier(name)
        assert classifier
