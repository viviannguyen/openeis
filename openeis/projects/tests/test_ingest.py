# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2014, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# or favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#
#}}}

'''

'''
import json
import os
import inspect
import io

from rest_framework.test import APIRequestFactory
from rest_framework.test import APIClient
from rest_framework import status
from django.test import TestCase
from django.test.client import Client
from django.http.response import HttpResponseForbidden
from django.contrib.auth.models import User

from openeis.projects.storage.ingest import ingest_files, IngestError
from openeis.projects.views import perform_ingestion


SENSOR_MAP_JSON = '''
{
  "version": 1,
  "files": {
    "File 1": {
      "extra": {},
      "signature": {
        "headers": ["Date", "Hillside OAT [F]", "Main Meter [kW]", "Boiler Gas [kBtu/hr]"]
      },
      "timestamp": {"columns": ["Date"], "format": "%m/%d/%Y %H:%M"}
    }
  },
  "sensors": {
    "Site 1/Sensor 1": {
      "type": "OutdoorAirTemperature",
      "unit": "fahrenheit",
      "file": "File 1",
      "column": "Hillside OAT [F]"
    },
    "Site 1/Building 1": {
      "level": "building",
      "attributes": {
        "address": {
          "address": "123 Main St",
          "city": "Anytown",
          "state": "WA",
          "zip_code": "99123"
        }
      }
    },
    "Site 1": {
      "level": "site",
      "attributes": {
        "address": {
          "address": "123 Main St",
          "city": "Anytown",
          "state": "WA",
          "zip_code": "99123"
        }
      }
    },
    "Site 1/Building 1/System 1/Sensor 2": {
      "system": "RTU",
      "type": "OutdoorAirTemperature",
      "unit": "fahrenheit",
      "file": "File 1",
      "column": 2
    },
    "Site 2/Sensor 1": {
      "type": "OutdoorAirTemperature",
      "unit": "fahrenheit",
      "file": "File 1",
      "column": 3
    }
  },
  "extra": {"ham": ["and", "beans"]}
}
'''

GOOD_DATA = '''Date,Hillside OAT [F],Main Meter [kW],Boiler Gas [kBtu/hr]
9/29/2009 15:00,74.72,280.08,186.52
9/29/2009 16:00,75.52,259.67,169.82
9/29/2009 17:00,75.78,221.92,113.88
9/29/2009 18:00,76.19,145.24,54.74
9/29/2009 19:00,76.72,121.85,11.58
9/29/2009 20:00,76.3,113.72,11.17
9/29/2009 21:00,76.88,111.22,21.41
9/29/2009 22:00,77.16,107.01,29.2
9/29/2009 23:00,76.44,108.45,81.02
9/30/2009 0:00,76.9,116.66,170.73
9/30/2009 1:00,77.29,119.1,246.17
9/30/2009 2:00,76.99,117.57,213.78
9/30/2009 3:00,78.99,121.98,215.91
9/30/2009 4:00,78.99,139.2,385.73
9/30/2009 5:00,78.99,151.42,477.32
9/30/2009 6:00,78.99,162.47,701.29
9/30/2009 7:00,78.99,189.76,691.95
9/30/2009 8:00,78.99,221.91,624.79
9/30/2009 9:00,78.99,228.19,454.43
9/30/2009 10:00,78.99,236.93,468.05
9/30/2009 11:00,78.99,239.53,308.18
9/30/2009 12:00,78.99,246.81,268.58
9/30/2009 13:00,78.99,249.38,229.05
9/30/2009 14:00,71.81,258.76,205.13
9/30/2009 15:00,71.14,261.77,204.11
9/30/2009 16:00,73.83,234.85,181.09
9/30/2009 17:00,73.33,198.26,129.27
9/30/2009 18:00,73.93,140.55,53.38
9/30/2009 19:00,73.75,124.13,20.04'''

# missing datetime on record 2
# invalid float on line 3
# missing date on line 4
# missing all columns on line 7
#
ERROR_DATA = '''Date,Hillside OAT [F],Main Meter [kW],Boiler Gas [kBtu/hr]
9/29/2009 15:00,74.72,280.08,186.52
,75.52,259.67,169.82
9/29/2009 17:00,a75.78,221.92,113.88
18:00,76.19,145.24,54.74
9/29/2009 19:00,76.72,121.85,11.58
9/29/2009 20:00,76.3,113.72,11.17
9/29/2009 21:00,76.3,113.72,11.17
9/29/2009 22:00,77.16,107.01,29.2
9/29/2009 23:00,76.44,108.45,81.02
9/30/2009,76.9,116.66,170.73
9/30/2009 1:00,77.29,119.1,246.17
9/30/2009 2:00,76.99,117.57,213.78
9/30/2009 3:00,,121.98,215.91
9/30/2009 4:00,,139.2,385.73
9/30/2009 5:00,,151.42,477.32
9/30/2009 6:00,,162.47,701.29
9/30/2009 7:00,,189.76,691.95'''


class TestIngestApi(TestCase):
    '''
    These functions test the ingest_files method of openeis.projects.storage.ingest module.  For testing
    we are using the an io.StringIO object created from different inputs.
    '''
    # Use the fixture with a test_user|test and a project 1.
    fixtures = ['db_dump_test_userPWtest_project.json']


    def setUp(self):
        '''
        Initializes the sensor map and sets up a good_data and error_data instance variables
        to run tests against.
        '''
        # Set this up so that we are ready to use whichever we need in the functions.
        self.sensormap = json.loads(SENSOR_MAP_JSON)
        # Create file like object for reading from.
        # Add size attribute so that it works with the ingest.py correctly
        data_io = io.StringIO(GOOD_DATA)
        data_io.size = len(GOOD_DATA)
        # modified to use timezone data.
        self.good_data = [('File 1', {'file_name': data_io, 'time_zone': 'America/Los_Angeles'})]

        # Do the same as above for the error data.
        data_io = io.StringIO(ERROR_DATA)
        data_io.size = len(ERROR_DATA)
        self.error_data = [('File 1', data_io)]




    def test_ingest_good_data_all_rows_ingested(self):

        expected_rows = len(GOOD_DATA.split(sep='\n'))
        files = ingest_files(self.sensormap, self.good_data)

        self.assertIsNotNone(files, "ingest_files returned none value")
        rowcount = 1
        for fileIngest in files:
            self.assertIsNotNone(fileIngest)
            self.assertEqual(4, len(fileIngest.sensors))

            for row in fileIngest.rows:
                for col in row.columns:
                    self.assertFalse(isinstance(col, IngestError), "The column had an error!")

                rowcount += 1
        # Returns 1 based numbering from where the data actually starts.
        self.assertEqual(expected_rows, rowcount, 'Invalid rowcount.')

    '''
    def test_ingest_bad_data(self):
        # Ignore the header
        expected_rows = len(ERROR_DATA.split(sep='\n')) - 1
        files = ingest_files(self.sensormap, self.error_data)

        self.assertIsNotNone(files, "ingest_files returned none value")
        rowcount = 2 # Data starts at line 2
        for fileIngest in files:
            self.assertIsNotNone(fileIngest)
            self.assertEqual(4, len(fileIngest.sensors))

            for row in fileIngest.rows:
                self.assertEqual(rowcount, row.line_num)
                self.assertTrue(row.line_num > 0)
                self.assertTrue(isinstance(row.line_num, int), "Invalid row.line_number on {}".format(rowcount))
                print(row.line_num)
                for col in row.columns:
                    self.assertFalse(isinstance(col, IngestError), "The column had an error!")

                rowcount += 1
        # Returns 1 based numbering from where the data actually starts.
        self.assertEqual(expected_rows, rowcount, 'Invalid rowcount.')
    '''

    def test_save_good_data(self):
        expected_rows = len(ERROR_DATA.split(sep='\n')) - 1
        files = ingest_files(self.sensormap, self.error_data)

