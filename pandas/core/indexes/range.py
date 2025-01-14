from datetime import timedelta
import operator
from sys import getsizeof
from typing import Union
import warnings

import numpy as np

from pandas._libs import index as libindex, lib
import pandas.compat as compat
from pandas.compat.numpy import function as nv
from pandas.util._decorators import Appender, cache_readonly

from pandas.core.dtypes import concat as _concat
from pandas.core.dtypes.common import (
    ensure_python_int, is_int64_dtype, is_integer, is_scalar,
    is_timedelta64_dtype)
from pandas.core.dtypes.generic import (
    ABCDataFrame, ABCSeries, ABCTimedeltaIndex)

from pandas.core import ops
import pandas.core.common as com
import pandas.core.indexes.base as ibase
from pandas.core.indexes.base import Index, _index_shared_docs
from pandas.core.indexes.numeric import Int64Index

from pandas.io.formats.printing import pprint_thing


class RangeIndex(Int64Index):
    """
    Immutable Index implementing a monotonic integer range.

    RangeIndex is a memory-saving special case of Int64Index limited to
    representing monotonic ranges. Using RangeIndex may in some instances
    improve computing speed.

    This is the default index type used
    by DataFrame and Series when no explicit index is provided by the user.

    Parameters
    ----------
    start : int (default: 0), or other RangeIndex instance
        If int and "stop" is not given, interpreted as "stop" instead.
    stop : int (default: 0)
    step : int (default: 1)
    name : object, optional
        Name to be stored in the index
    copy : bool, default False
        Unused, accepted for homogeneity with other index types.

    Attributes
    ----------
    start
    stop
    step

    Methods
    -------
    from_range

    See Also
    --------
    Index : The base pandas Index type.
    Int64Index : Index of int64 data.
    """

    _typ = 'rangeindex'
    _engine_type = libindex.Int64Engine
    _range = None  # type: range

    # check whether self._data has benn called
    _cached_data = None  # type: np.ndarray
    # --------------------------------------------------------------------
    # Constructors

    def __new__(cls, start=None, stop=None, step=None,
                dtype=None, copy=False, name=None, fastpath=None):

        if fastpath is not None:
            warnings.warn("The 'fastpath' keyword is deprecated, and will be "
                          "removed in a future version.",
                          FutureWarning, stacklevel=2)
            if fastpath:
                return cls._simple_new(start, stop, step, name=name)

        cls._validate_dtype(dtype)

        # RangeIndex
        if isinstance(start, RangeIndex):
            if name is None:
                name = start.name
            return cls._simple_new(name=name,
                                   **dict(start._get_data_as_items()))

        # validate the arguments
        if com._all_none(start, stop, step):
            raise TypeError("RangeIndex(...) must be called with integers")

        start = ensure_python_int(start) if start is not None else 0

        if stop is None:
            start, stop = 0, start
        else:
            stop = ensure_python_int(stop)

        step = ensure_python_int(step) if step is not None else 1
        if step == 0:
            raise ValueError("Step must not be zero")

        return cls._simple_new(start, stop, step, name)

    @classmethod
    def from_range(cls, data, name=None, dtype=None, **kwargs):
        """
        Create RangeIndex from a range object.

        Returns
        -------
        RangeIndex
        """
        if not isinstance(data, range):
            raise TypeError(
                '{0}(...) must be called with object coercible to a '
                'range, {1} was passed'.format(cls.__name__, repr(data)))

        start, stop, step = data.start, data.stop, data.step
        return cls(start, stop, step, dtype=dtype, name=name, **kwargs)

    @classmethod
    def _simple_new(cls, start, stop=None, step=None, name=None,
                    dtype=None, **kwargs):
        result = object.__new__(cls)

        # handle passed None, non-integers
        if start is None and stop is None:
            # empty
            start, stop, step = 0, 0, 1

        if start is None or not is_integer(start):
            try:
                return cls(start, stop, step, name=name, **kwargs)
            except TypeError:
                return Index(start, stop, step, name=name, **kwargs)

        result._range = range(start, stop or 0, step or 1)

        result.name = name
        for k, v in kwargs.items():
            setattr(result, k, v)

        result._reset_identity()
        return result

    # --------------------------------------------------------------------

    @staticmethod
    def _validate_dtype(dtype):
        """ require dtype to be None or int64 """
        if not (dtype is None or is_int64_dtype(dtype)):
            raise TypeError('Invalid to pass a non-int64 dtype to RangeIndex')

    @cache_readonly
    def _constructor(self):
        """ return the class to use for construction """
        return Int64Index

    @property
    def _data(self):
        """
        An int array that for performance reasons is created only when needed.

        The constructed array is saved in ``_cached_data``. This allows us to
        check if the array has been created without accessing ``_data`` and
        triggering the construction.
        """
        if self._cached_data is None:
            self._cached_data = np.arange(self.start, self.stop, self.step,
                                          dtype=np.int64)
        return self._cached_data

    @cache_readonly
    def _int64index(self):
        return Int64Index._simple_new(self._data, name=self.name)

    def _get_data_as_items(self):
        """ return a list of tuples of start, stop, step """
        rng = self._range
        return [('start', rng.start),
                ('stop', rng.stop),
                ('step', rng.step)]

    def __reduce__(self):
        d = self._get_attributes_dict()
        d.update(dict(self._get_data_as_items()))
        return ibase._new_Index, (self.__class__, d), None

    # --------------------------------------------------------------------
    # Rendering Methods

    def _format_attrs(self):
        """
        Return a list of tuples of the (attr, formatted_value)
        """
        attrs = self._get_data_as_items()
        if self.name is not None:
            attrs.append(('name', ibase.default_pprint(self.name)))
        return attrs

    def _format_data(self, name=None):
        # we are formatting thru the attributes
        return None

    def _format_with_header(self, header, na_rep='NaN', **kwargs):
        return header + list(map(pprint_thing, self._range))

    # --------------------------------------------------------------------
    _deprecation_message = ("RangeIndex.{} is deprecated and will be "
                            "removed in a future version. Use RangeIndex.{} "
                            "instead")

    @cache_readonly
    def start(self):
        """
        The value of the `start` parameter (``0`` if this was not supplied)
        """
        # GH 25710
        return self._range.start

    @property
    def _start(self):
        """
        The value of the `start` parameter (``0`` if this was not supplied)

         .. deprecated:: 0.25.0
            Use ``start`` instead.
        """
        warnings.warn(self._deprecation_message.format("_start", "start"),
                      DeprecationWarning, stacklevel=2)
        return self.start

    @cache_readonly
    def stop(self):
        """
        The value of the `stop` parameter
        """
        return self._range.stop

    @property
    def _stop(self):
        """
        The value of the `stop` parameter

         .. deprecated:: 0.25.0
            Use ``stop`` instead.
        """
        # GH 25710
        warnings.warn(self._deprecation_message.format("_stop", "stop"),
                      DeprecationWarning, stacklevel=2)
        return self.stop

    @cache_readonly
    def step(self):
        """
        The value of the `step` parameter (``1`` if this was not supplied)
        """
        # GH 25710
        return self._range.step

    @property
    def _step(self):
        """
        The value of the `step` parameter (``1`` if this was not supplied)

         .. deprecated:: 0.25.0
            Use ``step`` instead.
        """
        # GH 25710
        warnings.warn(self._deprecation_message.format("_step", "step"),
                      DeprecationWarning, stacklevel=2)
        return self.step

    @cache_readonly
    def nbytes(self):
        """
        Return the number of bytes in the underlying data.
        """
        rng = self._range
        return getsizeof(rng) + sum(getsizeof(getattr(rng, attr_name))
                                    for attr_name in ['start', 'stop', 'step'])

    def memory_usage(self, deep=False):
        """
        Memory usage of my values

        Parameters
        ----------
        deep : bool
            Introspect the data deeply, interrogate
            `object` dtypes for system-level memory consumption

        Returns
        -------
        bytes used

        Notes
        -----
        Memory usage does not include memory consumed by elements that
        are not components of the array if deep=False

        See Also
        --------
        numpy.ndarray.nbytes
        """
        return self.nbytes

    @property
    def dtype(self):
        return np.dtype(np.int64)

    @property
    def is_unique(self):
        """ return if the index has unique values """
        return True

    @cache_readonly
    def is_monotonic_increasing(self):
        return self._range.step > 0 or len(self) <= 1

    @cache_readonly
    def is_monotonic_decreasing(self):
        return self._range.step < 0 or len(self) <= 1

    @property
    def has_duplicates(self):
        return False

    def __contains__(self, key: Union[int, np.integer]) -> bool:
        hash(key)
        try:
            key = ensure_python_int(key)
        except TypeError:
            return False
        return key in self._range

    @Appender(_index_shared_docs['get_loc'])
    def get_loc(self, key, method=None, tolerance=None):
        if is_integer(key) and method is None and tolerance is None:
            try:
                return self._range.index(key)
            except ValueError:
                raise KeyError(key)
        return super().get_loc(key, method=method, tolerance=tolerance)

    def tolist(self):
        return list(self._range)

    @Appender(_index_shared_docs['_shallow_copy'])
    def _shallow_copy(self, values=None, **kwargs):
        if values is None:
            name = kwargs.get("name", self.name)
            return self._simple_new(
                name=name, **dict(self._get_data_as_items()))
        else:
            kwargs.setdefault('name', self.name)
            return self._int64index._shallow_copy(values, **kwargs)

    @Appender(ibase._index_shared_docs['copy'])
    def copy(self, name=None, deep=False, dtype=None, **kwargs):
        self._validate_dtype(dtype)
        if name is None:
            name = self.name
        return self.from_range(self._range, name=name)

    def _minmax(self, meth):
        no_steps = len(self) - 1
        if no_steps == -1:
            return np.nan
        elif ((meth == 'min' and self.step > 0) or
              (meth == 'max' and self.step < 0)):
            return self.start

        return self.start + self.step * no_steps

    def min(self, axis=None, skipna=True, *args, **kwargs):
        """The minimum value of the RangeIndex"""
        nv.validate_minmax_axis(axis)
        nv.validate_min(args, kwargs)
        return self._minmax('min')

    def max(self, axis=None, skipna=True, *args, **kwargs):
        """The maximum value of the RangeIndex"""
        nv.validate_minmax_axis(axis)
        nv.validate_max(args, kwargs)
        return self._minmax('max')

    def argsort(self, *args, **kwargs):
        """
        Returns the indices that would sort the index and its
        underlying data.

        Returns
        -------
        argsorted : numpy array

        See Also
        --------
        numpy.ndarray.argsort
        """
        nv.validate_argsort(args, kwargs)

        if self._range.step > 0:
            return np.arange(len(self))
        else:
            return np.arange(len(self) - 1, -1, -1)

    def equals(self, other):
        """
        Determines if two Index objects contain the same elements.
        """
        if isinstance(other, RangeIndex):
            return self._range == other._range
        return super().equals(other)

    def intersection(self, other, sort=False):
        """
        Form the intersection of two Index objects.

        Parameters
        ----------
        other : Index or array-like
        sort : False or None, default False
            Sort the resulting index if possible

            .. versionadded:: 0.24.0

            .. versionchanged:: 0.24.1

               Changed the default to ``False`` to match the behaviour
               from before 0.24.0.

        Returns
        -------
        intersection : Index
        """
        self._validate_sort_keyword(sort)

        if self.equals(other):
            return self._get_reconciled_name_object(other)

        if not isinstance(other, RangeIndex):
            return super().intersection(other, sort=sort)

        if not len(self) or not len(other):
            return self._simple_new(None)

        first = self._range[::-1] if self.step < 0 else self._range
        second = other._range[::-1] if other.step < 0 else other._range

        # check whether intervals intersect
        # deals with in- and decreasing ranges
        int_low = max(first.start, second.start)
        int_high = min(first.stop, second.stop)
        if int_high <= int_low:
            return self._simple_new(None)

        # Method hint: linear Diophantine equation
        # solve intersection problem
        # performance hint: for identical step sizes, could use
        # cheaper alternative
        gcd, s, t = self._extended_gcd(first.step, second.step)

        # check whether element sets intersect
        if (first.start - second.start) % gcd:
            return self._simple_new(None)

        # calculate parameters for the RangeIndex describing the
        # intersection disregarding the lower bounds
        tmp_start = first.start + (second.start - first.start) * \
            first.step // gcd * s
        new_step = first.step * second.step // gcd
        new_index = self._simple_new(tmp_start, int_high, new_step)

        # adjust index to limiting interval
        new_start = new_index._min_fitting_element(int_low)
        new_index = self._simple_new(new_start, new_index.stop, new_index.step)

        if (self.step < 0 and other.step < 0) is not (new_index.step < 0):
            new_index = new_index[::-1]
        if sort is None:
            new_index = new_index.sort_values()
        return new_index

    def _min_fitting_element(self, lower_limit):
        """Returns the smallest element greater than or equal to the limit"""
        no_steps = -(-(lower_limit - self.start) // abs(self.step))
        return self.start + abs(self.step) * no_steps

    def _max_fitting_element(self, upper_limit):
        """Returns the largest element smaller than or equal to the limit"""
        no_steps = (upper_limit - self.start) // abs(self.step)
        return self.start + abs(self.step) * no_steps

    def _extended_gcd(self, a, b):
        """
        Extended Euclidean algorithms to solve Bezout's identity:
           a*x + b*y = gcd(x, y)
        Finds one particular solution for x, y: s, t
        Returns: gcd, s, t
        """
        s, old_s = 0, 1
        t, old_t = 1, 0
        r, old_r = b, a
        while r:
            quotient = old_r // r
            old_r, r = r, old_r - quotient * r
            old_s, s = s, old_s - quotient * s
            old_t, t = t, old_t - quotient * t
        return old_r, old_s, old_t

    def _union(self, other, sort):
        """
        Form the union of two Index objects and sorts if possible

        Parameters
        ----------
        other : Index or array-like

        sort : False or None, default None
            Whether to sort resulting index. ``sort=None`` returns a
            mononotically increasing ``RangeIndex`` if possible or a sorted
            ``Int64Index`` if not. ``sort=False`` always returns an
            unsorted ``Int64Index``

            .. versionadded:: 0.25.0

        Returns
        -------
        union : Index
        """
        if not len(other) or self.equals(other) or not len(self):
            return super()._union(other, sort=sort)

        if isinstance(other, RangeIndex) and sort is None:
            start_s, step_s = self.start, self.step
            end_s = self.start + self.step * (len(self) - 1)
            start_o, step_o = other.start, other.step
            end_o = other.start + other.step * (len(other) - 1)
            if self.step < 0:
                start_s, step_s, end_s = end_s, -step_s, start_s
            if other.step < 0:
                start_o, step_o, end_o = end_o, -step_o, start_o
            if len(self) == 1 and len(other) == 1:
                step_s = step_o = abs(self.start - other.start)
            elif len(self) == 1:
                step_s = step_o
            elif len(other) == 1:
                step_o = step_s
            start_r = min(start_s, start_o)
            end_r = max(end_s, end_o)
            if step_o == step_s:
                if ((start_s - start_o) % step_s == 0 and
                        (start_s - end_o) <= step_s and
                        (start_o - end_s) <= step_s):
                    return self.__class__(start_r, end_r + step_s, step_s)
                if ((step_s % 2 == 0) and
                        (abs(start_s - start_o) <= step_s / 2) and
                        (abs(end_s - end_o) <= step_s / 2)):
                    return self.__class__(start_r,
                                          end_r + step_s / 2,
                                          step_s / 2)
            elif step_o % step_s == 0:
                if ((start_o - start_s) % step_s == 0 and
                        (start_o + step_s >= start_s) and
                        (end_o - step_s <= end_s)):
                    return self.__class__(start_r, end_r + step_s, step_s)
            elif step_s % step_o == 0:
                if ((start_s - start_o) % step_o == 0 and
                        (start_s + step_o >= start_o) and
                        (end_s - step_o <= end_o)):
                    return self.__class__(start_r, end_r + step_o, step_o)
        return self._int64index._union(other, sort=sort)

    @Appender(_index_shared_docs['join'])
    def join(self, other, how='left', level=None, return_indexers=False,
             sort=False):
        if how == 'outer' and self is not other:
            # note: could return RangeIndex in more circumstances
            return self._int64index.join(other, how, level, return_indexers,
                                         sort)

        return super().join(other, how, level, return_indexers, sort)

    def _concat_same_dtype(self, indexes, name):
        return _concat._concat_rangeindex_same_dtype(indexes).rename(name)

    def __len__(self):
        """
        return the length of the RangeIndex
        """
        return len(self._range)

    @property
    def size(self):
        return len(self)

    def __getitem__(self, key):
        """
        Conserve RangeIndex type for scalar and slice keys.
        """
        super_getitem = super().__getitem__

        if is_scalar(key):
            if not lib.is_integer(key):
                raise IndexError("only integers, slices (`:`), "
                                 "ellipsis (`...`), numpy.newaxis (`None`) "
                                 "and integer or boolean "
                                 "arrays are valid indices")
            n = com.cast_scalar_indexer(key)
            if n != key:
                return super_getitem(key)
            try:
                return self._range[key]
            except IndexError:
                raise IndexError("index {key} is out of bounds for axis 0 "
                                 "with size {size}".format(key=key,
                                                           size=len(self)))
        if isinstance(key, slice):
            new_range = self._range[key]
            return self.from_range(new_range, name=self.name)

        # fall back to Int64Index
        return super_getitem(key)

    def __floordiv__(self, other):
        if isinstance(other, (ABCSeries, ABCDataFrame)):
            return NotImplemented

        if is_integer(other) and other != 0:
            if (len(self) == 0 or
                    self.start % other == 0 and
                    self.step % other == 0):
                start = self.start // other
                step = self.step // other
                stop = start + len(self) * step
                return self._simple_new(start, stop, step, name=self.name)
            if len(self) == 1:
                start = self.start // other
                return self._simple_new(start, start + 1, 1, name=self.name)
        return self._int64index // other

    def all(self) -> bool:
        return 0 not in self._range

    def any(self) -> bool:
        return any(self._range)

    @classmethod
    def _add_numeric_methods_binary(cls):
        """ add in numeric methods, specialized to RangeIndex """

        def _make_evaluate_binop(op, step=False):
            """
            Parameters
            ----------
            op : callable that accepts 2 parms
                perform the binary op
            step : callable, optional, default to False
                op to apply to the step parm if not None
                if False, use the existing step
            """

            def _evaluate_numeric_binop(self, other):
                if isinstance(other, (ABCSeries, ABCDataFrame)):
                    return NotImplemented
                elif isinstance(other, ABCTimedeltaIndex):
                    # Defer to TimedeltaIndex implementation
                    return NotImplemented
                elif isinstance(other, (timedelta, np.timedelta64)):
                    # GH#19333 is_integer evaluated True on timedelta64,
                    # so we need to catch these explicitly
                    return op(self._int64index, other)
                elif is_timedelta64_dtype(other):
                    # Must be an np.ndarray; GH#22390
                    return op(self._int64index, other)

                other = self._validate_for_numeric_binop(other, op)
                attrs = self._get_attributes_dict()
                attrs = self._maybe_update_attributes(attrs)

                left, right = self, other

                try:
                    # apply if we have an override
                    if step:
                        with np.errstate(all='ignore'):
                            rstep = step(left.step, right)

                        # we don't have a representable op
                        # so return a base index
                        if not is_integer(rstep) or not rstep:
                            raise ValueError

                    else:
                        rstep = left.step

                    with np.errstate(all='ignore'):
                        rstart = op(left.start, right)
                        rstop = op(left.stop, right)

                    result = self.__class__(rstart, rstop, rstep, **attrs)

                    # for compat with numpy / Int64Index
                    # even if we can represent as a RangeIndex, return
                    # as a Float64Index if we have float-like descriptors
                    if not all(is_integer(x) for x in
                               [rstart, rstop, rstep]):
                        result = result.astype('float64')

                    return result

                except (ValueError, TypeError, ZeroDivisionError):
                    # Defer to Int64Index implementation
                    return op(self._int64index, other)
                    # TODO: Do attrs get handled reliably?

            name = '__{name}__'.format(name=op.__name__)
            return compat.set_function_name(_evaluate_numeric_binop, name, cls)

        cls.__add__ = _make_evaluate_binop(operator.add)
        cls.__radd__ = _make_evaluate_binop(ops.radd)
        cls.__sub__ = _make_evaluate_binop(operator.sub)
        cls.__rsub__ = _make_evaluate_binop(ops.rsub)
        cls.__mul__ = _make_evaluate_binop(operator.mul, step=operator.mul)
        cls.__rmul__ = _make_evaluate_binop(ops.rmul, step=ops.rmul)
        cls.__truediv__ = _make_evaluate_binop(operator.truediv,
                                               step=operator.truediv)
        cls.__rtruediv__ = _make_evaluate_binop(ops.rtruediv,
                                                step=ops.rtruediv)


RangeIndex._add_numeric_methods()
