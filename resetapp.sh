#!/bin/sh
# resets all files and directories with hopefully ok permissions 
# and initializes the database
DATAPATH=data # in current directory, used in other places as well..
DATAFILE=app.db # in that directory
INITSQL=app.sql # the initialization SQL script

# set up app specific database
mkdir -p $DATAPATH
sqlite3 $DATAPATH/$DATAFILE < $INITSQL
chmod a+rwx $DATAPATH
chmod a+rwx $DATAPATH/$DATAFILE
# fix other permissions
chmod a+r *.py

# python 2
chmod --quiet a+r *.pyc
# python 3
chmod --quiet a+rx __pycache__
chmod --quiet a+r __pycache__/*

chmod a+r *.ini
chmod a+r *.wsgi
