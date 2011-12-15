#!/usr/bin/env python
# -*- coding: utf-8 -*-
################################################################################
#
#  qooxdoo - the new era of web development
#
#  http://qooxdoo.org
#
#  Copyright:
#    2006-2010 1&1 Internet AG, Germany, http://www.1und1.de
#
#  License:
#    LGPL: http://www.gnu.org/licenses/lgpl.html
#    EPL: http://www.eclipse.org/org/documents/epl-v10.php
#    See the LICENSE file in the project's top-level directory for details.
#
#  Authors:
#    * Sebastian Werner (wpbasti)
#    * Thomas Herchenroeder (thron7)
#
################################################################################

import os, time, functools, gc
import cPickle as pickle
from misc import filetool
from misc.securehash import sha_construct
from generator.runtime.ShellCmd import ShellCmd
from generator.runtime.Log import Log

check_file     = u".cache_check_file"
CACHE_REVISION = 28982 # increment this when existing caches need clearing

class Cache(object):


    ##
    # kwargs:
    #  'console' : Log()
    #  'cache/downloads' : path
    #  'interruptRegistry' : generator.runtime.InterruptRegistry (mandatory)
    #  'cache/invalidate-on-tool-change' : True|False
    #
    def __init__(self, path, **kwargs):
        self._cache_revision = CACHE_REVISION
        self._path           = path
        self._context        = kwargs
        self._console        = kwargs.get('console', Log())
        self._downloads      = kwargs.get("cache/downloads", path+"/downloads")
        self._check_file     = os.path.join(self._path, check_file)
        self._console.debug("Initializing cache...")
        self._console.indent()
        self._check_path(self._path)
        self._context['interruptRegistry'].register(self._unlock_files)
        self._assureCacheIsValid()  # checks and pot. clears existing cache
        self._console.outdent()
        self._cache_objects = {}
        self._memcache = {}
        self._dirty = set()
        return

    def __getstate__(self):
        raise pickle.PickleError("Never pickle generator.runtime.Cache.")

    def _assureCacheIsValid(self, ):
        self._toolChainIsNewer = self._checkToolsNewer()
        if self._toolChainIsNewer:
            if self._context.get("cache/invalidate-on-tool-change", False):
                self._console.info("Cleaning compile cache, as tool chain has changed")
                self.cleanCompileCache()  # will also remove checkFile
            else:
                self._console.warn("! Detected changed tool chain; you might want to clear the cache.")
        self._update_checkfile()
        return


    def _update_checkfile(self, ):
        fd  = os.open(self._check_file, os.O_CREAT|os.O_RDWR, 0666)  # open or create (portable form of os.mknod)
        numbytes = os.write(fd, str(self._cache_revision))
        os.close(fd)
        if numbytes < 1:
            raise IOError("Cannot write cache check file '%s'" % check_file)
        return

    def _checkToolsNewer(self, ):
        cacheRevision = self.getCacheFileVersion()
        if not cacheRevision:
            return True
        elif self._cache_revision != cacheRevision:
            return True  # current caches rev is different from that of the Cache class
        else:
            return False


    ##
    # returns the number in the check file on disk, if existent, None otherwise

    def getCacheFileVersion(self):
        if not os.path.isfile(self._check_file):
            return None
        else:
            cacheRevision = open(self._check_file, "r").read()
            try:
                cacheRevision = int(cacheRevision)
            except:
                return None
            return cacheRevision

    ##
    # delete the files in the compile cache

    def cleanCompileCache(self):
        self._check_path(self._path)
        self._console.info("Deleting compile cache")
        for f in os.listdir(self._path):   # currently, just delete the files in the top-level dir
            file = os.path.join(self._path, f)
            if os.path.isfile(file):
                os.unlink(file)
        self._update_checkfile()


    def cleanDownloadCache(self):
        if self._downloads:
            downdir = self._downloads
            if os.path.splitdrive(downdir)[1] == os.sep:
                raise RuntimeError, "I'm not going to delete '/' recursively!"
            self._console.info("Deleting download cache")
            ShellCmd().rm_rf(downdir)


    ##
    # make sure there is a cache directory to work with (no r/w test currently)

    def _check_path(self, path):
        self._console.indent()
        self._console.debug("Checking path '%s'" % path)
        if not os.path.exists(path):
            self._console.debug("Creating non-existing cache directory")
            filetool.directory(path)
            self._update_checkfile()
        elif not os.path.isdir(path):
            raise RuntimeError, "The cache path is not a directory: %s" % path
        else: # it's an existing directory
            # defer read/write access test to the first call of read()/write()
            self._console.debug("Using existing directory")
            pass
        self._console.outdent()

    ##
    # clean up lock files interrupt handler

    def _unlock_files(self):
        for file in self._locked_files:
            try:
                filetool.unlock(file)
                self._console.debug("Cleaned up lock for file: %r" % file)
            except: # file might not exists since adding to _lock_files and actually locking is not atomic
                pass   # no sense to do much fancy in an interrupt handler


    ##
    # warn about newer tool chain interrupt handler

    def _warn_toolchain(self):
        if self._toolChainIsNewer:
            self._console.warn("Detected newer tool chain; you might want to run 'generate.py distclean', then re-run this job.")


    ##
    # create a file name from a cacheId

    def filename(self, cacheId):
        cacheId = cacheId.encode('utf-8')
        splittedId = cacheId.split("-")
        
        if len(splittedId) == 1:
            return cacheId
                
        baseId = splittedId.pop(0)
        digestId = sha_construct("-".join(splittedId)).hexdigest()

        return "%s-%s" % (baseId, digestId)
        
    ##
    # Read an object from cache.
    # 
    # @param dependsOn  file name to compare cache file against
    # @param memory     if read from disk keep value also in memory; improves subsequent access
    def read(self, cacheId, dependsOn=None, memory=False, keepLock=False):
        print cacheId
        if dependsOn:
            source_timestamp = os.stat(dependsOn).st_mtime
        else:
            # no dependency?
            source_timestamp = 0 

        if cacheId in self._memcache:
            timestamp, content = self._memcache[cacheId]

            # Expired cache item?
            if source_timestamp > timestamp:
                del self._memcache[cacheId]
                self._dirty.discard(cacheId)
                print "oops. expired memcache"
                return None, source_timestamp

            print "got item from memcache"
        else:
            # File cache
            filetool.directory(self._path)
            cacheFile = os.path.join(self._path, self.filename(cacheId))

            filetool.lock(cacheFile)
            try:
                fobj = open(cacheFile, 'rb')
                gc.disable()
                try:
                    # read timestamp first
                    timestamp = pickle.load(fobj)
                    if source_timestamp > timestamp:
                        # expired cache item -> ignore
                        print "oops. expired"
                        return None, source_timestamp

                    # Not expired? Read content
                    content = pickle.loads(fobj.read().decode('zlib'))
                finally:
                    gc.enable()
                    fobj.close()
            except IOError:
                print "error while reading"
                return None, source_timestamp
            finally:
                filetool.unlock(cacheFile)

            # self._memcache[cacheId] = source_timestamp, content
            # self._dirty.discard(cacheId)

        self._cache_objects[id(content)] = cacheId
        print "returning object: %s -> %s" % (
            cacheId, source_timestamp)
        return content, source_timestamp

    ##
    # Write an object to cache.
    #
    # @param memory         keep value also in memory; improves subsequent access
    # @param writeToFile    write value to disk
    def write(self, cacheId, content, memory=False, writeToFile=True, keepLock=False):
        read_cacheId = self._cache_objects.get(id(content))
        if read_cacheId and read_cacheId != cacheId:
            # content was read from different cacheId. 
            # The content of this previous cacheId is now
            # invalidated in memory.
            if read_cacheId in self._memcache:
                print "invalidating previous cache key %s while writing to %s" % (
                    read_cacheId, cacheId)
                del self._memcache[read_cacheId]

        print "writing to %s" % (cacheId,)

        self._memcache[cacheId] = time.time(), content
        self._dirty.add(cacheId)

        if len(self._dirty) > 20:
            self.flush()
            self.zap()

    def flush(self):
        print "flushing %d dirty keys. %d total" % (
            len(self._dirty), len(self._memcache))
       
        filetool.directory(self._path)
        for cacheId, (content_timestamp, content) in \
                self._memcache.iteritems():

            # not changed? no need to write
            if cacheId not in self._dirty:
                continue

            cacheFile = os.path.join(self._path, self.filename(cacheId))

            fobj = open(cacheFile, 'wb')
            try:
                pickle.dump(content_timestamp, fobj, 2)
                fobj.write(pickle.dumps(content, 2).encode('zlib'))
            finally:
                fobj.close()

            self._dirty.remove(cacheId)

    def zap(self):
        self._memcache = {}
        self._dirty = set()
