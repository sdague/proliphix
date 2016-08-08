#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_proliphix
----------------------------------

Tests for `proliphix` module.
"""

import unittest
from unittest import mock

import proliphix
import proliphix.proliphix as px


class TestProliphix(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_oid(self):
        self.assertEqual('1.2', px._get_oid('DevName'))
        self.assertEqual('4.1.13', px._get_oid('AverageTemp'))
        self.assertEqual(None, px._get_oid('AverageTemp2'))

    # we don't want to actually do the clock drift work during tests
    # here.
    @mock.patch('proliphix.PDP._clock_drift')
    @mock.patch('requests.post')
    def test_update(self, rp, cd):
        pdp = proliphix.PDP(mock.sentinel.host,
                            mock.sentinel.user,
                            mock.sentinel.passwd)
        pdp.update()
        rp.assert_called_once_with(
            "http://%s/get" % mock.sentinel.host,
            auth=(mock.sentinel.user, mock.sentinel.passwd),
            data=('OID1.2=&OID2.5.1=&OID4.1.1=&OID4.1.11=&OID4.1.13'
                  '=&OID4.1.2=&OID4.1.4=&OID4.1.5='
                  '&OID4.1.6=&OID4.5.1=&OID4.5.3=&OID4.5.5=&OID4.5.6=')
            )

    @mock.patch('requests.post')
    def test_set_vals(self, rp):
        pdp = proliphix.PDP(mock.sentinel.host,
                            mock.sentinel.user,
                            mock.sentinel.passwd)
        pdp.setback_heat = 69.1
        rp.assert_called_once_with(
            "http://%s/pdp" % mock.sentinel.host,
            auth=(mock.sentinel.user, mock.sentinel.passwd),
            data='OID4.1.5=691&submit=Submit')

if __name__ == '__main__':
    import sys
    sys.exit(unittest.main())
