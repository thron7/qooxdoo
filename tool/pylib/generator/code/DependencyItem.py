#!/usr/bin/env python
# -*- coding: utf-8 -*-
################################################################################
#
#  qooxdoo - the new era of web development
#
#  http://qooxdoo.org
#
#  Copyright:
#    2006-2011 1&1 Internet AG, Germany, http://www.1und1.de
#
#  License:
#    LGPL: http://www.gnu.org/licenses/lgpl.html
#    EPL: http://www.eclipse.org/org/documents/epl-v10.php
#    See the LICENSE file in the project's top-level directory for details.
#
#  Authors:
#    * Thomas Herchenroeder (thron7)
#
################################################################################

import types
from operator import itemgetter

class DependencyItem(tuple):
    __slots__ = () 
    # _fields = ('name', 'attribute', 'requestor', 'line', 'isLoadDep', 'isCall', 'needsRecursion') 

    def __new__(_cls, name, attribute, requestor, line=-1, isLoadDep=False, isCall=False, needsRecursion=False):
        return tuple.__new__(_cls, (name, attribute, requestor, line, [isLoadDep], isCall, needsRecursion)) 

    def __repr__(self):
        return "<DepItem>:" + self.name + "#" + self.attribute
    def __str__(self):
        return self.name + "#" + self.attribute
    def __eq__(self, other):
        return (self.name == other.name and self.attribute == other.attribute
                and self.requestor == other.requestor and self.line == other.line
                )
    def __hash__(self):
        return hash(self.name + self.attribute)

    def __getnewargs__(self):
        return tuple(self) 

    name = property(itemgetter(0))
    attribute = property(itemgetter(1))
    requestor = property(itemgetter(2))
    line = property(itemgetter(3))

    # isLoadDep is mutable
    def get_isLoadDep(self):
        return self[4][0]
    def set_isLoadDep(self, value):
        self[4][0] = value
    isLoadDep = property(get_isLoadDep, set_isLoadDep)

    isCall = property(itemgetter(5))
    needsRecursion = property(itemgetter(6))
