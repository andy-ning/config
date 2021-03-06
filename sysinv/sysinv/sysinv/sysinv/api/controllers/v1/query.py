# coding: utf-8
# Copyright © 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 IBM Corp.
# Copyright © 2013 eNovance <licensing@enovance.com>
# Copyright Ericsson AB 2013. All rights reserved
#
# Authors: Doug Hellmann <doug.hellmann@dreamhost.com>
#          Angus Salkeld <asalkeld@redhat.com>
#          Eoghan Glynn <eglynn@redhat.com>
#          Julien Danjou <julien@danjou.info>
#          Ildiko Vancsa <ildiko.vancsa@ericsson.com>
#          Balazs Gibizer <balazs.gibizer@ericsson.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# Copyright (c) 2013-2015 Wind River Systems, Inc.
#

import ast
import functools
import inspect
import six
import wsme
from wsme import types as wtypes

from oslo_log import log
from oslo_utils import strutils
from oslo_utils import timeutils
from sysinv._i18n import _

LOG = log.getLogger(__name__)

operation_kind = wtypes.Enum(str, 'lt', 'le', 'eq', 'ne', 'ge', 'gt')


class _Base(wtypes.Base):

    @classmethod
    def from_db_model(cls, m):
        return cls(**(m.as_dict()))

    @classmethod
    def from_db_and_links(cls, m, links):
        return cls(links=links, **(m.as_dict()))

    def as_dict(self, db_model):
        valid_keys = inspect.getargspec(db_model.__init__)[0]
        if 'self' in valid_keys:
            valid_keys.remove('self')
        return self.as_dict_from_keys(valid_keys)

    def as_dict_from_keys(self, keys):
        return dict((k, getattr(self, k))
                    for k in keys
                    if hasattr(self, k) and
                    getattr(self, k) != wsme.Unset)


class Query(_Base):
    """Query filter.
    """

    # The data types supported by the query.
    _supported_types = ['integer', 'float', 'string', 'boolean']

    # Functions to convert the data field to the correct type.
    _type_converters = {'integer': int,
                        'float': float,
                        'boolean': functools.partial(
                            strutils.bool_from_string, strict=True),
                        'string': six.text_type,
                        'datetime': timeutils.parse_isotime}

    _op = None  # provide a default

    def get_op(self):
        return self._op or 'eq'

    def set_op(self, value):
        self._op = value

    field = wtypes.text
    "The name of the field to test"

    # op = wsme.wsattr(operation_kind, default='eq')
    # this ^ doesn't seem to work.
    op = wsme.wsproperty(operation_kind, get_op, set_op)
    "The comparison operator. Defaults to 'eq'."

    value = wtypes.text
    "The value to compare against the stored data"

    type = wtypes.text
    "The data type of value to compare against the stored data"

    def __repr__(self):
        # for logging calls
        return '<Query %r %s %r %s>' % (self.field,
                                        self.op,
                                        self.value,
                                        self.type)

    @classmethod
    def sample(cls):
        return cls(field='resource_id',
                   op='eq',
                   value='bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
                   type='string'
                   )

    def as_dict(self):
        return self.as_dict_from_keys(['field', 'op', 'type', 'value'])

    def _get_value_as_type(self, forced_type=None):
        """Convert metadata value to the specified data type.

        This method is called during metadata query to help convert the
        querying metadata to the data type specified by user. If there is no
        data type given, the metadata will be parsed by ast.literal_eval to
        try to do a smart converting.

        NOTE (flwang) Using "_" as prefix to avoid an InvocationError raised
        from wsmeext/sphinxext.py. It's OK to call it outside the Query class.
        Because the "public" side of that class is actually the outside of the
        API, and the "private" side is the API implementation. The method is
        only used in the API implementation, so it's OK.

        :returns: metadata value converted with the specified data type.
        """
        type = forced_type or self.type
        try:
            converted_value = self.value
            if not type:
                try:
                    converted_value = ast.literal_eval(self.value)
                except (ValueError, SyntaxError):
                    msg = _('Failed to convert the metadata value %s'
                            ' automatically') % (self.value)
                    LOG.debug(msg)
            else:
                if type not in self._supported_types:
                    # Types must be explicitly declared so the
                    # correct type converter may be used. Subclasses
                    # of Query may define _supported_types and
                    # _type_converters to define their own types.
                    raise TypeError()
                converted_value = self._type_converters[type](self.value)
        except ValueError:
            msg = _('Failed to convert the value %(value)s'
                    ' to the expected data type %(type)s.') % \
                {'value': self.value, 'type': type}
            raise wsme.exc.ClientSideError(msg)
        except TypeError:
            msg = _('The data type %(type)s is not supported. The supported'
                    ' data type list is: %(supported)s') % \
                {'type': type, 'supported': self._supported_types}
            raise wsme.exc.ClientSideError(msg)
        except Exception:
            msg = _('Unexpected exception converting %(value)s to'
                    ' the expected data type %(type)s.') % \
                {'value': self.value, 'type': type}
            raise wsme.exc.ClientSideError(msg)
        return converted_value
