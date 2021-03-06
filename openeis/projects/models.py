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

import contextlib
import json
import jsonschema
import posixpath
import random
import string

from django.contrib.auth.models import User
from django.db import connections, models
from django.db.models.query import QuerySet
from django.core.exceptions import ValidationError

import jsonschema.exceptions

from .protectedmedia import ProtectedFileSystemStorage
from .storage import sensormap
from .storage.csvfile import CSVFile


class JSONString(str):
    pass


class JSONField(models.TextField, metaclass=models.SubfieldBase):

    description = 'JSON encoded object'

    def to_python(self, value):
        if value is None or value == '':
            return value
        if not isinstance(value, str) or isinstance(value, JSONString):
            return value
        try:
            result = json.loads(value)
        except ValueError as e:
            raise ValidationError('Invalid JSON data: {}'.format(e))
        if isinstance(result, str):
            return JSONString(result)
        return result

    def get_prep_value(self, value):
        try:
            return json.dumps(value, separators=(',', ':'))
        except TypeError:
            raise ValidationError('Cannot serialize object to JSON')

    def value_to_string(self, obj):
        return super()._get_val_from_obj(obj)



class Organization(models.Model):
    '''Group and manage users by organization.'''

    name = models.CharField(max_length=100)
    members = models.ManyToManyField(
            User, through='Membership', related_name='organizations')

    def __str__(self):
        return self.name


class Membership(models.Model):
    '''Intermediate table for Organization/User relationship.'''

    organization = models.ForeignKey(Organization)
    user = models.ForeignKey(User)
    is_admin = models.BooleanField(verbose_name='Administrator status',
            help_text='Designates whether the user can manage organization '
                      'membership.')

    class Meta:
        verbose_name_plural = 'Membership'

    def __str__(self):
        return '{} {} of {}'.format(
                self.user.get_full_name() or '@' + self.user.username,
                'administrator' if self.is_admin else 'member',
                self.organization)


class Project(models.Model):
    '''Organizes and groups a users files, mappings, and results.'''

    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, related_name='projects')

    def __str__(self):
        return self.name


def _data_file_path(instance, filename):
    return posixpath.join('projects', str(instance.project.pk), filename)


class DataFile(models.Model):
    '''Represents an uploaded data file to feed applications.'''

    _ts_schema = {
        "type": "object",
        "required": ["columns"],
        "properties": {
            "columns": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": {
                            "oneOf": [
                                {"type": "string"},
                                {"type": "integer", "minimum": 0}
                            ]
                        },
                        "minItems": 1,
                        "uniqueItems": True
                    },
                    {"type": "string"},
                    {"type": "integer", "minimum": 0}
                ]
            },
            "format": {"type": ["string"]}
        },
        "additionalProperties": False
    }

    project = models.ForeignKey(Project, related_name='files')
    file = models.FileField(
            upload_to=_data_file_path, storage=ProtectedFileSystemStorage())
    uploaded = models.DateTimeField(
            auto_now_add=True, help_text='Date and time file was uploaded')
    comments = models.CharField(max_length=200, blank=True)
    timestamp = JSONField(blank=True)
    time_zone = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return self.file.name

    def csv_head(self, count=15):
        file = self.file
        if file.closed:
            file.open()
        rows = []
        with contextlib.closing(file):
            csv_file = CSVFile(file)
            if (csv_file.has_header):
                count += 1;
            for row in csv_file:
                rows.append(row)
                if len(rows) >= count:
                    break
            return csv_file.has_header, rows

    def clean_fields(self, exclude=None):
        '''Validate JSON against schema.'''
        super().clean_fields(exclude=exclude)
        if (exclude and 'timestamp' in exclude or
                self.timestamp is None or self.timestamp == ''):
            return
        validator = jsonschema.Draft4Validator(self._ts_schema)
        try:
            validator.validate(self.timestamp)
        except jsonschema.ValidationError as e:
            raise ValidationError({'timestamp' + ''.join('[{!r}]'.format(name)
                                   for name in e.path): [e.message]})


_CODE_CHOICES = string.ascii_letters + string.digits

def _verification_code():
    return ''.join(random.choice(_CODE_CHOICES) for i in range(50))


class AccountVerification(models.Model):
    account = models.ForeignKey(User)
    initiated = models.DateTimeField(auto_now_add=True)
    code = models.CharField(max_length=50, unique=True,
                            default=_verification_code)
    what = models.CharField(max_length=20)
    data = JSONField(blank=True)


class SensorMapDefinition(models.Model):
    project = models.ForeignKey(Project, related_name='sensor_maps')
    name = models.CharField(max_length=100)
    map = JSONField()

    class Meta:
        unique_together = ('project', 'name')

    def __str__(self):
        return self.name

    def __repr__(self):
        return '<{}: {}, {}>'.format(
                self.__class__.__name__, self.project, self.name)

    def clean_fields(self, exclude=None):
        '''Validate JSON against sensor map schema.'''
        super().clean_fields(exclude=exclude)
        if exclude and 'map' in exclude:
            return
        schema = sensormap.Schema()
        errors = schema.validate(self.map)
        if not errors:
            return
        raise ValidationError({('map' + ''.join('[{!r}]'.format(name)
                                for name in path)): value
                               for path, value in errors.items()})


class SensorIngest(models.Model):
    map = models.ForeignKey(SensorMapDefinition, related_name='ingests')
    # time of ingest
    start = models.DateTimeField(auto_now_add=True)
    end = models.DateTimeField(null=True, default=None)

    @property
    def logs(self):
        return [log for file in self.files.all() for log in file.logs.all()]


class SensorIngestFile(models.Model):
    ingest = models.ForeignKey(SensorIngest, related_name='files')
    # name matches a file in the sensor map definition
    name = models.CharField(max_length=255)
    file = models.ForeignKey(DataFile, related_name='ingests')

    class Meta:
        unique_together = ('ingest', 'name')


class SensorIngestLog(models.Model):
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    LOG_LEVEL_CHOICES = ((INFO, 'Info'), (WARNING, 'Warning'),
                         (ERROR, 'Error'), (CRITICAL, 'Critical'))

    file = models.ForeignKey(SensorIngestFile, related_name='logs', null=True)
    row = models.IntegerField()
    # Timestamps can include multiple columns
    column = models.CommaSeparatedIntegerField(max_length=20)
    level = models.SmallIntegerField(choices=LOG_LEVEL_CHOICES)
    message = models.CharField(max_length=255)


class Sensor(models.Model):
    BOOLEAN = 'b'
    FLOAT = 'f'
    INTEGER = 'i'
    STRING = 's'

    DATA_TYPE_CHOICES = ((BOOLEAN, 'boolean'), (FLOAT, 'float'),
                         (INTEGER, 'integer'), (STRING, 'string'))

    map = models.ForeignKey(SensorMapDefinition, related_name='sensors')
    # name matches the sensor path in the definition
    name = models.CharField(max_length=255)
    data_type = models.CharField(max_length=1, choices=DATA_TYPE_CHOICES)

    class Meta:
        unique_together = ('map', 'name')

    @property
    def data(self):
        return getattr(self, self.get_data_type_display() + 'sensordata_set')

    @property
    def data_class(self):
        return globals()[self.get_data_type_display().capitalize() + 'SensorData']


class SensorDataQuerySet(QuerySet):
    class pg_trunc(dict):
        def __missing__(self, key):
            if key not in {'minute', 'hour', 'day', 'month', 'year'}:
                raise KeyError(key)
            return "date_trunc('{0}', {{field}})".format(key)

    trunc_funcs = {
        "mysql": {
            "year": "strftime('%%Y', {field})",
            "month": "strftime('%%Y-%%m', {field})",
            "day": "strftime('%%Y-%%m-%%d', {field})",
            "hour": "strftime('%%Y-%%m-%%d %%H', {field})",
            "minute": "strftime('%%Y-%%m-%%d %%H:%%i', {field})",
        },
        "oracle": {
            "year": "trunc({field}, 'YEAR')",
            "month": "trunc({field}, 'MONTH')",
            "day": "trunc({field}, 'DAY')",
            "hour": "trunc({field}, 'HH24')",
            "minute": "trunc({field}, 'MI')",
        },
        "postgresql": pg_trunc(),
        "sqlite": {
            "year": "strftime('%%Y', {field})",
            "month": "strftime('%%Y-%%m', {field})",
            "day": "strftime('%%Y-%%m-%%d', {field})",
            "hour": "strftime('%%Y-%%m-%%d %%H', {field})",
            "minute": "strftime('%%Y-%%m-%%d %%H:%%M', {field})",
        },
    }

    def trunc_date(self, kind, *args, **kwargs):
        '''Truncate a date field to the level indicated by kind.

        kind must be one of 'year', 'month', 'day', 'hour', or 'minute'.
        args and kwargs contain field names to truncate. Names in args
        retain the same name while those in values of kwargs get named
        according to the key.
        '''
        backend = connections[self.db].vendor
        try:
            trunc = self.trunc_funcs[backend]
        except KeyError:
            raise NotImplementedError('group_by is not implemented for the '
                                      '{} database backend'.format(backend))
        try:
            func = trunc[kind]
        except KeyError:
            raise ValueError('invalid truncation kind: {}'.format(kind))
        for arg in args:
            if arg in kwargs:
                raise ValueError('field given twice: {}'.format(arg))
            kwargs[arg] = arg
        select = {dest: func.format(field=source)
                  for dest, source in kwargs.items()}
        return self.extra(select=select) if select else self

    def timeseries(self, *, trunc_kind=None, aggregate=None):
        '''Return timeseries pairs from the table.

        Returns 2-tuples of time-value pairs. If trunc_kind is given,
        the time is truncated to the given precision. If aggregate is
        given, the series values are aggregated according to the given
        aggregation method and grouped by the time.
        '''
        queryset = self
        if trunc_kind:
            queryset = queryset.trunc_date(trunc_kind, 'time')
        if aggregate:
            queryset = queryset.values('time').annotate(value=aggregate('value'))
        return queryset.values_list('time', 'value')


class SensorDataManager(models.Manager):
    def get_queryset(self):
        return SensorDataQuerySet(self.model)
    @property
    def timeseries(self):
        return self.get_queryset().timeseries
    @property
    def trunc_date(self):
        return self.get_queryset().trunc_date



class BaseSensorData(models.Model):
    sensor = models.ForeignKey(Sensor)
    ingest = models.ForeignKey(SensorIngest)
    time = models.DateTimeField()
    time_zone = models.CharField(max_length=50, default='UTC')

    class Meta:
        abstract = True
        ordering = ['time']
        get_latest_by = 'time'


class BooleanSensorData(BaseSensorData):
    value = models.NullBooleanField()
    objects = SensorDataManager()

class FloatSensorData(BaseSensorData):
    value = models.FloatField(null=True)
    objects = SensorDataManager()

class IntegerSensorData(BaseSensorData):
    value = models.IntegerField(null=True)
    objects = SensorDataManager()

class StringSensorData(BaseSensorData):
    value = models.TextField(null=True)
    objects = SensorDataManager()


class Analysis(models.Model):
    '''A run of a single application against a single dataset.'''

    name = models.CharField(max_length=100)
    dataset = models.ForeignKey(SensorIngest, related_name='analysis')
    application = models.CharField(max_length=255)
    '''
    Expected configuration to be a json string like
    {
        "inputs": {
            "key": ["ISB1/OutdoorAirTemperature","TOPIC2"]
        },
        "parameters": {
            "config1": "value1",
            "config2": intvalue
        }
    }
    '''
    configuration = JSONField()
    debug = models.BooleanField(default=False)
    # Ran successfully or not
    status = models.CharField(max_length=50, default='queued')
    # Initially queued
    added = models.DateTimeField(auto_now_add=True)
    started = models.DateTimeField(null=True, default=None)
    ended = models.DateTimeField(null=True, default=None)
    progress_percent = models.FloatField(default=0)
    reports = JSONField()


def _share_key():
    return ''.join(random.choice(_CODE_CHOICES) for i in range(16))


class SharedAnalysis(models.Model):
    analysis = models.OneToOneField(Analysis, primary_key=True)
    key = models.CharField(max_length=16, default=_share_key)


class AppOutput(models.Model):
    analysis = models.ForeignKey(Analysis, related_name='app_output')
    name = models.CharField(max_length=255)
    fields = JSONField()
