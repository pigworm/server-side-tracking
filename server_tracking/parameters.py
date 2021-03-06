# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import namedtuple
import itertools
import six

from .exceptions import InvalidParametersException


UrlParameter = UP = namedtuple('UrlParameter', ['url_component', 'required'])
UP.__new__.__defaults__ = (False, )
VariableParameter = VP = namedtuple('VariableParameter', ['index'])


def _get_property(item):
    def get_item(self):
        return self._params.get(item)

    def set_item(self, value):
        if value is not None:
            self._params[item] = value
        elif item in self._params:
            del self._params[item]

    def del_item(self):
        try:
            del self._params[item]
        except KeyError:
            pass

    return property(get_item, set_item, del_item)


_META_INFO_NAME = str('MetaInfo')
_META_INFO_FIELDS = ['preset_prefix', 'index_prefix', 'custom_prefix', 'item_prefix']
_META_INFO_DEFAULT = {field_name: '' for field_name in _META_INFO_FIELDS}
_META_INFO_DEFAULT['abstract'] = False


def _copy_meta(cls_meta, meta, fields):
    if cls_meta:
        for field in fields:
            if hasattr(cls_meta, field):
                setattr(meta, field, getattr(cls_meta, field))


class ParameterMeta(type):
    def __new__(mcs, name, bases, dct):
        new_cls = super(ParameterMeta, mcs).__new__(mcs, name, bases, dct)
        param_base = getattr(new_cls, 'meta', None)
        new_cls.meta = meta = type(_META_INFO_NAME, (object, ), _META_INFO_DEFAULT)()
        _copy_meta(param_base, meta, _META_INFO_FIELDS)
        _copy_meta(dct.get('Meta'), meta, _META_INFO_FIELDS + ['abstract'])
        cls_parameters = [(p_name, p)
                          for p_name, p in six.iteritems(dct)
                          if isinstance(p, UrlParameter)]
        cls_c_parameters = [(p_name, p)
                            for p_name, p in six.iteritems(dct)
                            if isinstance(p, VariableParameter)]
        if param_base:
            meta.parameters = parameters = param_base.parameters[:]
            parameters.extend(cls_parameters)
            meta.custom_parameters = c_parameters = param_base.custom_parameters[:]
            c_parameters.extend(cls_c_parameters)
            meta.parameter_names = parameter_names = param_base.parameter_names[:]
            parameter_names.extend(i[0] for i in itertools.chain(cls_parameters, cls_c_parameters))
        else:
            meta.parameters = parameters = cls_parameters
            meta.custom_parameters = c_parameters = cls_c_parameters
            meta.parameter_names = [i[0] for i in itertools.chain(cls_parameters, cls_c_parameters)]
        meta.required_components = required_components = set()
        meta.component_parameters = component_rev = {}
        if not getattr(meta, 'abstract', False):
            custom_prefix = meta.custom_prefix
            for p_name, param in parameters:
                url_comp = param.url_component
                if param.required:
                    required_components.add(url_comp)
                setattr(new_cls, p_name, _get_property(url_comp))
                component_rev[url_comp] = p_name
            for p_name, param in c_parameters:
                url_comp = '{0}{1}'.format(custom_prefix, param.index)
                setattr(new_cls, p_name, _get_property(url_comp))
                component_rev[url_comp] = p_name
        return new_cls


class AbstractUrlGenerator(six.with_metaclass(ParameterMeta)):
    class Meta(object):
        abstract = True

    def __init__(self, params=None, **kwargs):
        if self.meta.abstract:
            raise ValueError("Cannot instantiate an abstract UrlGenerator class.")
        if isinstance(params, self.__class__):
            self._params = params._params.copy()
        else:
            self._params = {}
            self.update(params)
        self.update_from_kwargs(kwargs)

    def __len__(self):
        return len(self._params)

    def __repr__(self):
        cp = self.meta.component_parameters
        items = ', '.join('{0}={1!r}'.format(cp[k], v)
                          for k, v in six.iteritems(self._params))
        return '<{0}: {1}>'.format(self.__class__.__name__, items)

    def _update_from_dict(self, d):
        names = self.meta.parameter_names
        for k, v in six.iteritems(d):
            if k in names:
                setattr(self, k, v)
            else:
                raise ValueError("Invalid field name '{0}'.".format(k))

    def copy(self):
        new_obj = self.__class__()
        new_obj._params = self._params.copy()
        return new_obj

    def update(self, other=None, **kwargs):
        if other:
            if isinstance(other, AbstractUrlGenerator):
                for name in self.meta.parameter_names:
                    setattr(self, name, getattr(other, name))
            elif isinstance(other, dict):
                self._update_from_dict(other)
            else:
                raise ValueError("Invalid type for update.")
        self.update_from_kwargs(kwargs)

    def update_from_kwargs(self, kwargs):
        names = self.meta.parameter_names
        for k, v in six.iteritems(kwargs):
            if k in names:
                if v is not None:
                    setattr(self, k, v)
            else:
                raise ValueError("Invalid field name '{0}'.".format(k))

    def is_empty(self):
        return not self._params

    def validate(self):
        missing = {self.meta.component_parameters[req]
                   for req in self.meta.required_components.difference(self._params)}
        if missing:
            raise InvalidParametersException("Parameters are required, but missing: {0}",
                                             ', '.join(missing))

    def url(self, *args, **kwargs):
        raise NotImplementedError("Method is not implemented.")


class UrlGenerator(AbstractUrlGenerator):
    class Meta(object):
        abstract = True

    def url(self, *args, **kwargs):
        self.validate()
        return self._params.copy()


class PrefixUrlGenerator(AbstractUrlGenerator):
    class Meta(object):
        abstract = True

    def __init__(self, *args, **kwargs):
        super(PrefixUrlGenerator, self).__init__(*args, **kwargs)
        if not self.meta.preset_prefix:
            raise ValueError("Meta value preset_prefix is not set.")
        if not self.meta.index_prefix:
            raise ValueError("Meta value index_prefix is not set.")

    def url(self, *args, **kwargs):
        self.validate()
        meta = self.meta
        prefix = '{0}{1}'.format(meta.preset_prefix, meta.index_prefix)
        params = {
            '{0}{1}'.format(prefix, key): value
            for key, value in six.iteritems(self._params)
        }
        return params


class EnumeratedUrlGenerator(AbstractUrlGenerator):
    class Meta(object):
        abstract = True

    def url(self, index, *args, **kwargs):
        self.validate()
        meta = self.meta
        prefix = '{0}{1}{2}'.format(meta.preset_prefix, meta.index_prefix, meta.item_prefix)
        enum_params = {
            '{0}{1}{2}'.format(prefix, index, key): value
            for key, value in six.iteritems(self._params)
        }
        return enum_params
