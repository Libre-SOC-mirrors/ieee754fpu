# SPDX-License-Identifier: LGPL-3-or-later
# See Notices.txt for copyright information

from enum import Enum
from typing import (Any, Callable, ClassVar, Generic, ItemsView, Iterable,
                    Iterator, KeysView, Literal, Mapping, Optional, Tuple,
                    TypeVar, Union, ValuesView, overload)


class ElWid(Enum):
    def __repr__(self) -> str: ...


class FpElWid(ElWid):
    F64 = 0
    F32 = 1
    F16 = 2
    BF16 = 3


class IntElWid(ElWid):
    I64 = 0
    I32 = 1
    I16 = 2
    I8 = 3


_T = TypeVar('_T')
_T1 = TypeVar('_T1')
_T2 = TypeVar('_T2')

_ElWid = Union[FpElWid, IntElWid]


class SimdMap(Generic[_T]):
    ALL_ELWIDTHS: ClassVar[Tuple[_ElWid, ...]]

    __map: Mapping[_ElWid, _T]

    @overload
    @staticmethod
    def extract_value_algo(values: None,
                           default: _T2 = None, *,
                           simd_map_get: Callable[["SimdMap[_T]"], _T],
                           mapping_get: Callable[[Mapping[_ElWid, _T]], _T],
                           ) -> _T2: ...

    @overload
    @staticmethod
    def extract_value_algo(values: SimdMap[_T],
                           default: _T2 = None, *,
                           simd_map_get: Callable[["SimdMap[_T]"], _T],
                           mapping_get: Callable[[Mapping[_ElWid, _T]], _T],
                           ) -> Union[_T, _T2]: ...

    @overload
    @staticmethod
    def extract_value_algo(values: Mapping[_ElWid, _T],
                           default: _T2 = None, *,
                           simd_map_get: Callable[["SimdMap[_T]"], _T],
                           mapping_get: Callable[[Mapping[_ElWid, _T]], _T],
                           ) -> Union[_T, _T2]: ...

    @overload
    @staticmethod
    def extract_value_algo(values: _T,
                           default: _T2 = None, *,
                           simd_map_get: Callable[["SimdMap[_T]"], _T],
                           mapping_get: Callable[[Mapping[_ElWid, _T]], _T],
                           ) -> Union[_T, _T2]: ...

    @overload
    @classmethod
    def extract_value(cls,
                      elwid: _ElWid,
                      values: None,
                      default: _T2 = None) -> _T2: ...

    @overload
    @classmethod
    def extract_value(cls,
                      elwid: _ElWid,
                      values: SimdMap[_T],
                      default: _T2 = None) -> Union[_T, _T2]: ...

    @overload
    @classmethod
    def extract_value(cls,
                      elwid: _ElWid,
                      values: Mapping[_ElWid, _T],
                      default: _T2 = None) -> Union[_T, _T2]: ...

    @overload
    @classmethod
    def extract_value(cls,
                      elwid: _ElWid,
                      values: _T,
                      default: _T2 = None) -> Union[_T, _T2]: ...

    @overload
    def __init__(self, values: Optional[SimdMap[_T]] = None): ...
    @overload
    def __init__(self, values: Optional[Mapping[_ElWid, _T]] = None): ...
    @overload
    def __init__(self, values: Optional[_T] = None): ...

    @property
    def mapping(self) -> Mapping[_ElWid, _T]: ...

    def values(self) -> ValuesView[_T]: ...

    def keys(self) -> KeysView[_ElWid]: ...

    def items(self) -> ItemsView[_ElWid, _T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid],
                                   SimdMap[_T]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid],
                                   Mapping[_ElWid, Optional[_T]]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid],
                                   Optional[_T]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1],
                                   SimdMap[_T]],
                       __arg1: SimdMap[_T1],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1],
                                   Mapping[_ElWid, Optional[_T]]],
                       __arg1: SimdMap[_T1],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1],
                                   Optional[_T]],
                       __arg1: SimdMap[_T1],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1],
                                   SimdMap[_T]],
                       __arg1: Mapping[_ElWid, Optional[_T1]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1],
                                   Mapping[_ElWid, Optional[_T]]],
                       __arg1: Mapping[_ElWid, Optional[_T1]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1],
                                   Optional[_T]],
                       __arg1: Mapping[_ElWid, Optional[_T1]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1],
                                   SimdMap[_T]],
                       __arg1: Optional[_T1],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1],
                                   Mapping[_ElWid, Optional[_T]]],
                       __arg1: Optional[_T1],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1],
                                   Optional[_T]],
                       __arg1: Optional[_T1],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   SimdMap[_T]],
                       __arg1: SimdMap[_T1],
                       __arg2: SimdMap[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Mapping[_ElWid, Optional[_T]]],
                       __arg1: SimdMap[_T1],
                       __arg2: SimdMap[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Optional[_T]],
                       __arg1: SimdMap[_T1],
                       __arg2: SimdMap[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   SimdMap[_T]],
                       __arg1: Mapping[_ElWid, Optional[_T1]],
                       __arg2: SimdMap[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Mapping[_ElWid, Optional[_T]]],
                       __arg1: Mapping[_ElWid, Optional[_T1]],
                       __arg2: SimdMap[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Optional[_T]],
                       __arg1: Mapping[_ElWid, Optional[_T1]],
                       __arg2: SimdMap[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   SimdMap[_T]],
                       __arg1: Optional[_T1],
                       __arg2: SimdMap[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Mapping[_ElWid, Optional[_T]]],
                       __arg1: Optional[_T1],
                       __arg2: SimdMap[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Optional[_T]],
                       __arg1: Optional[_T1],
                       __arg2: SimdMap[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   SimdMap[_T]],
                       __arg1: SimdMap[_T1],
                       __arg2: Mapping[_ElWid, Optional[_T2]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Mapping[_ElWid, Optional[_T]]],
                       __arg1: SimdMap[_T1],
                       __arg2: Mapping[_ElWid, Optional[_T2]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Optional[_T]],
                       __arg1: SimdMap[_T1],
                       __arg2: Mapping[_ElWid, Optional[_T2]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   SimdMap[_T]],
                       __arg1: Mapping[_ElWid, Optional[_T1]],
                       __arg2: Mapping[_ElWid, Optional[_T2]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Mapping[_ElWid, Optional[_T]]],
                       __arg1: Mapping[_ElWid, Optional[_T1]],
                       __arg2: Mapping[_ElWid, Optional[_T2]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Optional[_T]],
                       __arg1: Mapping[_ElWid, Optional[_T1]],
                       __arg2: Mapping[_ElWid, Optional[_T2]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   SimdMap[_T]],
                       __arg1: Optional[_T1],
                       __arg2: Mapping[_ElWid, Optional[_T2]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Mapping[_ElWid, Optional[_T]]],
                       __arg1: Optional[_T1],
                       __arg2: Mapping[_ElWid, Optional[_T2]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Optional[_T]],
                       __arg1: Optional[_T1],
                       __arg2: Mapping[_ElWid, Optional[_T2]],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   SimdMap[_T]],
                       __arg1: SimdMap[_T1],
                       __arg2: Optional[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Mapping[_ElWid, Optional[_T]]],
                       __arg1: SimdMap[_T1],
                       __arg2: Optional[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Optional[_T]],
                       __arg1: SimdMap[_T1],
                       __arg2: Optional[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   SimdMap[_T]],
                       __arg1: Mapping[_ElWid, Optional[_T1]],
                       __arg2: Optional[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Mapping[_ElWid, Optional[_T]]],
                       __arg1: Mapping[_ElWid, Optional[_T1]],
                       __arg2: Optional[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Optional[_T]],
                       __arg1: Mapping[_ElWid, Optional[_T1]],
                       __arg2: Optional[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   SimdMap[_T]],
                       __arg1: Optional[_T1],
                       __arg2: Optional[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Mapping[_ElWid, Optional[_T]]],
                       __arg1: Optional[_T1],
                       __arg2: Optional[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[[_ElWid, _T1, _T2],
                                   Optional[_T]],
                       __arg1: Optional[_T1],
                       __arg2: Optional[_T2],
                       ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[..., SimdMap[_T]],
                       *args: Any) -> SimdMap[_T]:
        ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[..., Mapping[_ElWid, Optional[_T]]],
                       *args: Any) -> SimdMap[_T]:
        ...

    @overload
    @classmethod
    def map_with_elwid(cls,
                       f: Callable[..., Optional[_T]],
                       *args: Any) -> SimdMap[_T]:
        ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[],
                        SimdMap[_T]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[],
                        Mapping[_ElWid, Optional[_T]]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[],
                        Optional[_T]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1],
                        SimdMap[_T]],
            __arg1: SimdMap[_T1],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1],
                        Mapping[_ElWid, Optional[_T]]],
            __arg1: SimdMap[_T1],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1],
                        Optional[_T]],
            __arg1: SimdMap[_T1],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1],
                        SimdMap[_T]],
            __arg1: Mapping[_ElWid, Optional[_T1]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1],
                        Mapping[_ElWid, Optional[_T]]],
            __arg1: Mapping[_ElWid, Optional[_T1]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1],
                        Optional[_T]],
            __arg1: Mapping[_ElWid, Optional[_T1]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1],
                        SimdMap[_T]],
            __arg1: Optional[_T1],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1],
                        Mapping[_ElWid, Optional[_T]]],
            __arg1: Optional[_T1],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1],
                        Optional[_T]],
            __arg1: Optional[_T1],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        SimdMap[_T]],
            __arg1: SimdMap[_T1],
            __arg2: SimdMap[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Mapping[_ElWid, Optional[_T]]],
            __arg1: SimdMap[_T1],
            __arg2: SimdMap[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Optional[_T]],
            __arg1: SimdMap[_T1],
            __arg2: SimdMap[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        SimdMap[_T]],
            __arg1: Mapping[_ElWid, Optional[_T1]],
            __arg2: SimdMap[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Mapping[_ElWid, Optional[_T]]],
            __arg1: Mapping[_ElWid, Optional[_T1]],
            __arg2: SimdMap[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Optional[_T]],
            __arg1: Mapping[_ElWid, Optional[_T1]],
            __arg2: SimdMap[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        SimdMap[_T]],
            __arg1: Optional[_T1],
            __arg2: SimdMap[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Mapping[_ElWid, Optional[_T]]],
            __arg1: Optional[_T1],
            __arg2: SimdMap[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Optional[_T]],
            __arg1: Optional[_T1],
            __arg2: SimdMap[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        SimdMap[_T]],
            __arg1: SimdMap[_T1],
            __arg2: Mapping[_ElWid, Optional[_T2]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Mapping[_ElWid, Optional[_T]]],
            __arg1: SimdMap[_T1],
            __arg2: Mapping[_ElWid, Optional[_T2]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Optional[_T]],
            __arg1: SimdMap[_T1],
            __arg2: Mapping[_ElWid, Optional[_T2]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        SimdMap[_T]],
            __arg1: Mapping[_ElWid, Optional[_T1]],
            __arg2: Mapping[_ElWid, Optional[_T2]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Mapping[_ElWid, Optional[_T]]],
            __arg1: Mapping[_ElWid, Optional[_T1]],
            __arg2: Mapping[_ElWid, Optional[_T2]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Optional[_T]],
            __arg1: Mapping[_ElWid, Optional[_T1]],
            __arg2: Mapping[_ElWid, Optional[_T2]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        SimdMap[_T]],
            __arg1: Optional[_T1],
            __arg2: Mapping[_ElWid, Optional[_T2]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Mapping[_ElWid, Optional[_T]]],
            __arg1: Optional[_T1],
            __arg2: Mapping[_ElWid, Optional[_T2]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Optional[_T]],
            __arg1: Optional[_T1],
            __arg2: Mapping[_ElWid, Optional[_T2]],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        SimdMap[_T]],
            __arg1: SimdMap[_T1],
            __arg2: Optional[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Mapping[_ElWid, Optional[_T]]],
            __arg1: SimdMap[_T1],
            __arg2: Optional[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Optional[_T]],
            __arg1: SimdMap[_T1],
            __arg2: Optional[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        SimdMap[_T]],
            __arg1: Mapping[_ElWid, Optional[_T1]],
            __arg2: Optional[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Mapping[_ElWid, Optional[_T]]],
            __arg1: Mapping[_ElWid, Optional[_T1]],
            __arg2: Optional[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Optional[_T]],
            __arg1: Mapping[_ElWid, Optional[_T1]],
            __arg2: Optional[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        SimdMap[_T]],
            __arg1: Optional[_T1],
            __arg2: Optional[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Mapping[_ElWid, Optional[_T]]],
            __arg1: Optional[_T1],
            __arg2: Optional[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[[_T1, _T2],
                        Optional[_T]],
            __arg1: Optional[_T1],
            __arg2: Optional[_T2],
            ) -> SimdMap[_T]: ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[..., SimdMap[_T]],
            *args: Any) -> SimdMap[_T]:
        ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[..., Mapping[_ElWid, Optional[_T]]],
            *args: Any) -> SimdMap[_T]:
        ...

    @overload
    @classmethod
    def map(cls,
            f: Callable[..., Optional[_T]],
            *args: Any) -> SimdMap[_T]:
        ...

    @overload
    def get(self, elwid: _ElWid, default: Any = None, *,
            raise_key_error: Literal[True]) -> _T: ...

    @overload
    def get(self, elwid: _ElWid, default: _T2 = None, *,
            raise_key_error: bool = False) -> Union[_T, _T2]: ...

    def __iter__(self) -> Iterator[Tuple[_ElWid, _T]]: ...

    @overload
    def __add__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...
    @overload
    def __add__(self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...
    @overload
    def __add__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __add__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __radd__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __radd__(self, other: Mapping[_ElWid,
                                      Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __radd__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __radd__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __sub__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...
    @overload
    def __sub__(self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...
    @overload
    def __sub__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __sub__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __rsub__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __rsub__(self, other: Mapping[_ElWid,
                                      Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __rsub__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __rsub__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __mul__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...
    @overload
    def __mul__(self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...
    @overload
    def __mul__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __mul__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __rmul__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __rmul__(self, other: Mapping[_ElWid,
                                      Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __rmul__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __rmul__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __floordiv__(
        self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __floordiv__(
        self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __floordiv__(
        self, other: Optional[_T]) -> SimdMap[_T]: ...

    @overload
    def __floordiv__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __rfloordiv__(
        self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __rfloordiv__(
        self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __rfloordiv__(
        self, other: Optional[_T]) -> SimdMap[_T]: ...

    @overload
    def __rfloordiv__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __truediv__(
        self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __truediv__(
        self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __truediv__(
        self, other: Optional[_T]) -> SimdMap[_T]: ...

    @overload
    def __truediv__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __rtruediv__(
        self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __rtruediv__(
        self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __rtruediv__(
        self, other: Optional[_T]) -> SimdMap[_T]: ...

    @overload
    def __rtruediv__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __mod__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...
    @overload
    def __mod__(self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...
    @overload
    def __mod__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __mod__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __rmod__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __rmod__(self, other: Mapping[_ElWid,
                                      Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __rmod__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __rmod__(self, other: Any) -> SimdMap[Any]: ...

    def __abs__(self) -> SimdMap[_T]: ...

    @overload
    def __and__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...
    @overload
    def __and__(self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...
    @overload
    def __and__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __and__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __rand__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __rand__(self, other: Mapping[_ElWid,
                                      Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __rand__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __rand__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __divmod__(
        self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __divmod__(
        self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __divmod__(
        self, other: Optional[_T]) -> SimdMap[_T]: ...

    @overload
    def __divmod__(self, other: Any) -> SimdMap[Any]: ...

    def __ceil__(self) -> SimdMap[int]: ...

    def __float__(self) -> SimdMap[float]: ...

    def __floor__(self) -> SimdMap[int]: ...

    def __eq__(self, other: Any) -> bool: ...

    def __hash__(self) -> int: ...

    def __repr__(self) -> str: ...

    def __invert__(self) -> SimdMap[_T]: ...

    @overload
    def __lshift__(
        self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __lshift__(
        self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __lshift__(
        self, other: Optional[_T]) -> SimdMap[_T]: ...

    @overload
    def __lshift__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __rlshift__(
        self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __rlshift__(
        self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __rlshift__(
        self, other: Optional[_T]) -> SimdMap[_T]: ...

    @overload
    def __rlshift__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __rshift__(
        self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __rshift__(
        self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __rshift__(
        self, other: Optional[_T]) -> SimdMap[_T]: ...

    @overload
    def __rshift__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __rrshift__(
        self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __rrshift__(
        self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __rrshift__(
        self, other: Optional[_T]) -> SimdMap[_T]: ...

    @overload
    def __rrshift__(self, other: Any) -> SimdMap[Any]: ...

    def __neg__(self) -> SimdMap[_T]: ...

    def __pos__(self) -> SimdMap[_T]: ...

    @overload
    def __or__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...
    @overload
    def __or__(self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...
    @overload
    def __or__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __or__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __ror__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...
    @overload
    def __ror__(self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...
    @overload
    def __ror__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __ror__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __xor__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...
    @overload
    def __xor__(self, other: Mapping[_ElWid, Optional[_T]]) -> SimdMap[_T]: ...
    @overload
    def __xor__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __xor__(self, other: Any) -> SimdMap[Any]: ...

    @overload
    def __rxor__(self, other: SimdMap[_T]) -> SimdMap[_T]: ...

    @overload
    def __rxor__(self, other: Mapping[_ElWid,
                                      Optional[_T]]) -> SimdMap[_T]: ...

    @overload
    def __rxor__(self, other: Optional[_T]) -> SimdMap[_T]: ...
    @overload
    def __rxor__(self, other: Any) -> SimdMap[Any]: ...

    def missing_elwidths(self, *,
                         all_elwidths: Optional[Iterable[_ElWid]] = None,
                         ) -> Iterable[_ElWid]: ...


class SimdWHintMap(SimdMap[_T]):
    @overload
    @classmethod
    def extract_width_hint(cls,
                           values: None,
                           default: _T2 = None) -> _T2: ...

    @overload
    @classmethod
    def extract_width_hint(cls,
                           values: SimdMap[_T],
                           default: _T2 = None) -> Union[_T, _T2]: ...

    @overload
    @classmethod
    def extract_width_hint(cls,
                           values: Mapping[_ElWid, _T],
                           default: _T2 = None) -> Union[_T, _T2]: ...

    @overload
    @classmethod
    def extract_width_hint(cls,
                           values: _T,
                           default: _T2 = None) -> Union[_T, _T2]: ...

    @overload
    def __init__(self, values: Optional[SimdMap[_T]] = None, *,
                 width_hint: Optional[SimdMap[_T]] = None): ...

    @overload
    def __init__(self, values: Optional[Mapping[_ElWid, _T]] = None, *,
                 width_hint: Optional[SimdMap[_T]] = None): ...

    @overload
    def __init__(self, values: Optional[_T] = None, *,
                 width_hint: Optional[SimdMap[_T]] = None): ...

    @overload
    def __init__(self, values: Optional[SimdMap[_T]] = None, *,
                 width_hint: Optional[Mapping[_ElWid, _T]] = None): ...

    @overload
    def __init__(self, values: Optional[Mapping[_ElWid, _T]] = None, *,
                 width_hint: Optional[Mapping[_ElWid, _T]] = None): ...

    @overload
    def __init__(self, values: Optional[_T] = None, *,
                 width_hint: Optional[Mapping[_ElWid, _T]] = None): ...

    @overload
    def __init__(self, values: Optional[SimdMap[_T]] = None, *,
                 width_hint: Optional[_T] = None): ...

    @overload
    def __init__(self, values: Optional[Mapping[_ElWid, _T]] = None, *,
                 width_hint: Optional[_T] = None): ...

    @overload
    def __init__(self, values: Optional[_T] = None, *,
                 width_hint: Optional[_T] = None): ...

    @property
    def width_hint(self) -> _T: ...


XLEN: SimdWHintMap[int] = ...

DEFAULT_FP_VEC_EL_COUNTS: SimdMap[int] = ...

DEFAULT_INT_VEC_EL_COUNTS: SimdMap[int] = ...
