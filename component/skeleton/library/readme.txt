Library Skeleton - A qooxdoo application template
==================================================

This is a qooxdoo application skeleton which is used as a template. The 
'create-application.py' script (usually under tool/bin/create-application.py)
will use this and expand it into a self-contained qooxdoo application which 
can then be further extended. Please refer to the script and other documentation
for further information.

Running the 'build' job will create a library that can be used by non-qooxdoo
applications.

The 'test' job creates a basic testrunner script which depends on the
library (expected in the build/ folder).
You therefore have to run 'generate.py build' ahead of running the test scripts.
Then:
  cd test
  node node.js
  rhino rhino.js


short:: can be used as a library for non-qooxdoo applications
copy_file:: tool/data/generator/needs_generation.js source/script/custom.js
