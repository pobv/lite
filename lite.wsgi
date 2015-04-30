#!/usr/bin/python
# the she bang is just for the editors (emacs) to see that's python
# This is the main wsgi file used by apache mod_wsgi. It is ok to
# have several processes, as for each wsgi application (wsgi file)
# there is a different sub interpreter and according to mod_wsgi docu
# we can safely modify global variables, in this case:
# - sys.path to ensure we find all modules in the current directory
# - the state of the current directory in that interpreter to
#   allow reading without further path manipulation

import sys, os
sys.path.append(os.path.dirname(__file__)) # find modules
os.chdir(os.path.dirname(__file__)) # load files
from lite import application
