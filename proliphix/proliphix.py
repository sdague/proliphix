# -*- coding: utf-8 -*-
#
# Copyright 2016 Sean Dague
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# Changes/Additions added by Dwayne Zechman 6-Aug-2022
#   to add features necessary for Home Assistant integration
# - Added the following OID's
#   > 1.8 : SerialNum
#   > 4.1.3 : FanMode
# - Sorted the declaration of the OID's by number (okay this is just my OCD)
# - Added 2 additional constants for HVACMode
# - Added new property hvac_mode (R/W) to expose OID 4.1.1 directly in the API
# - Added setter for property hvac_state to make it R/W
# - Added new property serial_num (R/O) to expose OID 1.8 directly in the API
# - Added new property model (R/O) to expose OID 2.7.1 directly in the API
# - Added new property fan_mode (R/W) to expost OID 4.1.3 directly in the API
#
# This update was tested on the NT20e thermostat
#
"""Proliphix Network Thermostat

The Proliphix NT10e Thermostat is an ethernet connected thermostat. It
has a local HTTP interface that is based on get/set of OID values. A
complete collection of the API is available in this API doc:

https://github.com/sdague/thermostat.rb/blob/master/docs/PDP_API_R1_11.pdf
"""

import logging
import requests
import time
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


# The subset of oids which are useful for home-assistant, this might
# be expanded over time.
OIDS = {
    '1.2': 'DevName',
    '1.8': 'SerialNum',
    '1.10.9': 'SiteName',
    '2.5.1': 'Time',
    '2.7.1': 'ModelName',
    '4.1.1': 'HvacMode',
    '4.1.2': 'HvacState',
    '4.1.3': 'FanMode',
    '4.1.4': 'FanState',
    '4.1.5': 'SetbackHeat',
    '4.1.6': 'SetbackCool',
    '4.1.11': 'CurrentClass',
    '4.1.13': 'AverageTemp',
    '4.1.14': 'RelHumidity',
    '4.5.1': 'Heat1Usage',
    '4.5.3': 'Cool1Usage',
    '4.5.5': 'FanUsage',
    '4.5.6': 'LastUsageReset'
}

HVAC_MODE_OFF = 1
HVAC_MODE_HEAT = 2
HVAC_MODE_COOL = 3
HVAC_MOVE_AUTO = 4


def _get_oid(name):
    """Get OID by name/value."""
    for oid, value in OIDS.items():
        if value == name:
            return oid
    return None


def _all_oids():
    """Build a query string for all the OIDS we have."""
    return "&".join([("OID" + x + "=") for x in sorted(OIDS.keys())])


class PDP(object):
    """PDP class for interacting with Proliphix thermostat.

    OID states come back largely as enumerations, temp values come
    back as an int which is in decidegrees.

    The manual says don't make API calls more than once a minute for
    prolonged periods of time, so we only refresh the data on update,
    then fetch everything out of the cached data when needed.

    """
    def __init__(self, host, user, passwd):
        self._host = host
        self._user = user
        self._passwd = passwd
        self._data = {}

    def update(self):
        url = "http://%s/get" % self._host
        data = _all_oids()
        r = requests.post(url, auth=(self._user, self._passwd), data=data)
        self._data['Time'] = 0
        for line in r.text.split('&'):
            if line:
                oid, value = line.split('=')
                const = OIDS.get(oid[3:])
                if const:
                    self._data[const] = value
        self._clock_drift()
        logger.debug("PDP collected data %s" % self._data)

    def _clock_drift(self):
        now = int(time.time())
        # the clock on the proliphix is weird, and keeps track of DST
        # in a separate bit. They are clearly running the hardware
        # clock on localtime, which is a terrible idea. But this means
        # that regardless on what we think the drift is, we have to
        # set it like it's in standard time.
        is_dst = time.localtime().tm_isdst
        set_now = now - time.timezone
        if is_dst == 1:
            now -= time.altzone
        else:
            now -= time.timezone
        self._data['ActualTime'] = now
        drift = self._data['ActualTime'] - int(self._data['Time'])

        if abs(drift) > 60:
            logger.warning("PDP time drifted by %d seconds, resetting" % drift)
            self._set(Time=set_now)

    def _set(self, **kwargs):
        data = {}
        for key, value in kwargs.items():
            oid = _get_oid(key)
            if oid:
                data["OID%s" % oid] = value
        url = "http://%s/pdp" % self._host
        form_data = urlencode(data)
        form_data += "&submit=Submit"
        requests.post(url, auth=(self._user, self._passwd), data=form_data)

    @property
    def is_cooling(self):
        return int(self._data['HvacMode']) == HVAC_MODE_COOL

    @property
    def is_heating(self):
        return int(self._data['HvacMode']) == HVAC_MODE_HEAT

    @property
    def hvac_mode(self):
        return int(self._data['HvacMode'])

    @hvac_mode.setter
    def hvac_mode(self, val):
        self._data['HvacMode'] = int(val)
        self._set(HvacMode=self._data['HvacMode'])

    @property
    def cur_temp(self):
        return float(self._data['AverageTemp']) / 10

    @property
    def humidity(self):
        return int(self._data['RelHumidity'])

    @property
    def setback(self):
        if self.is_cooling:
            return self.setback_cool
        elif self.is_heating:
            return self.setback_heat

    @setback.setter
    def setback(self, val):
        if self.is_cooling:
            self.setback_cool = val
            return self.setback_cool
        elif self.is_heating:
            self.setback_heat = val
            return self.setback_heat

    @property
    def setback_heat(self):
        return float(self._data['SetbackHeat']) / 10

    @setback_heat.setter
    def setback_heat(self, val):
        self._data['SetbackHeat'] = int(val * 10)
        self._set(SetbackHeat=self._data['SetbackHeat'])

    @property
    def setback_cool(self):
        return float(self._data['SetbackCool']) / 10

    @setback_cool.setter
    def setback_cool(self, val):
        self._data['SetbackCool'] = int(val * 10)
        self._set(SetbackCool=self._data['SetbackCool'])

    @property
    def hvac_state(self):
        return int(self._data['HvacState'])

    @hvac_state.setter
    def hvac_state(self, val):
        self._data['HvacState'] = int(val)
        self._set(HvacState=self._data['HvacState'])

    @property
    def name(self):
        return "%s:%s" % (self._data['SiteName'], self._data['DevName'])

    @property
    def serial_num(self):
        return self._data['SerialNum']

    @property
    def model(self):
        return self._data['ModelName']

    @property
    def fan_state(self):
        if self._data['FanState'] == "2":
            return "On"
        else:
            return "Off"

    @property
    def fan_mode(self):
        return int(self._data['FanMode'])

    @fan_mode.setter
    def fan_mode(self, val):
        self._data['FanMode'] = int(val)
        self._set(FanMode=self._data['FanMode'])
