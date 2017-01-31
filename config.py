"read and evaluate initialization files on demand"

try:
    from configparser import ConfigParser
except:
    from ConfigParser import ConfigParser
import os.path
import datetime

import db
import app # ensure right database file is set


def read_config(configpath):
    "read a config configpath returning list of counters with initial values"
    confp = ConfigParser()
    confp.read(configpath)
    entries = []
    for which, zval in confp.items(confp.sections()[0]):
        entries.append(dict(which=int(which), z=int(zval)))
    return entries


def apply_config(configpath):
    "read and apply a configuration"
    configuration = read_config(configpath)
    ctimef = get_modified_configpath_fs(configpath) # of file
    with db.get_cursor() as cur:
        cur.execute("BEGIN EXCLUSIVE") # we are the only ones
        for dic in configuration:
            cur.execute(_APPLY_CONFIG_UPDATE, [dic["z"], dic["which"]])
        cur.execute(_UPDATE_MODIFIED_CONFIG, [str(ctimef), configpath])
        cur.connection.commit()
        return True # we initialized

_APPLY_CONFIG_UPDATE = "UPDATE counter SET z = ? WHERE which = ?"
_UPDATE_MODIFIED_CONFIG = u"""UPDATE admin SET modified = ?
  WHERE configpath = ?"""
def update_config(configpath=None):
    "applies configpath if modification date is newer than last recorded"
    if not configpath:
        configpath = get_configpath()
    ctimeu = get_modified_configpath_db(configpath) # last recorded
    if ctimeu == None: # db under load?, do not update now
        db.log_error("update_config: ctime is None, no update")
        return False
    ctimef = get_modified_configpath_fs(configpath) # of file
    # print("last modified: %d\n last updated: %d\n" % (ctimef, ctimeu))
    if ctimef > ctimeu: # need to update
        # diff = float(ctimef-ctimeu)/_MILLION
        # print("need to update, secs diff:", "%1.6f" % diff)
        configuration = read_config(configpath)
        # read configfile
        with db.get_cursor() as cur:
            try:
                cur.execute("BEGIN EXCLUSIVE") # we are the only ones
                # check that there has been no intermediate update
                #   a little bit like double checked locking...
                cur.execute(_SELECT_MODIFIED_CONFIG, [configpath])
                ctimeu2 = _int_from_fetchone(cur.fetchone())
                # print(ctimeu, ctimeu2)
                if ctimeu != ctimeu2: # unhealthy int equals (a float in there)
                    # no need to rollback, yet
                    msg = "update_config: somebody else updated it %d "
                    db.log_warn(msg % ctimeu2)
                    return False # somebody else has updated it
                # update values
                for dic in configuration:
                    cur.execute(_APPLY_CONFIG_UPDATE, [dic["z"], dic["which"]])
                # update modification date last, need to use very long number
                # that's why we hold TEXT not INTEGER or REAL
                cur.execute(_UPDATE_MODIFIED_CONFIG, [str(ctimef), configpath])
                cur.connection.commit()
                return True # we initialized
            except Exception as data: # may timeout
                db.log_error("update_config -> no update now", data)
                return False
    return False # no need to update

_SELECT_CONFIGPATH = u"SELECT configpath FROM admin"
def get_configpath():
    "gets the configpath"
    with db.get_cursor() as cur:
        try:
            cur.execute(_SELECT_CONFIGPATH)
            return db.one_or_none(cur)
        except Exception as data:
            db.log_error("get_configpath -> None", data)
            return None

_MILLION = 1000000
def get_modified_configpath_fs(configpath):
    "gets modified time from file system as long in microsecs"
    ctimef = os.path.getmtime(configpath) # of file
    return int(ctimef*_MILLION)

_SELECT_MODIFIED_CONFIG = u"SELECT modified FROM admin WHERE configpath = ?"
def get_modified_configpath_db(configpath):
    "gets recorded modified time as long in microsecs, no transaction"
    with db.get_cursor() as cur:
        try:
            cur.execute(_SELECT_MODIFIED_CONFIG, [configpath])
            return _int_from_fetchone(cur.fetchone())
        except Exception as data:
            db.log_error("get_modified_configpath_db -> None", data)
            return None # most likely no refresh of config file now

_EPOCH = 0 # 0 is epoch 1.1.1970 as timestamp
def _int_from_fetchone(one): # well a long int
    "computes an int from a text representation in a db, 0 for None"
    if not one:
        return _EPOCH
    number = one[0]
    if not number:
        return _EPOCH
    return int(number) # in microsecond accuracy

def fmt_ts(ustimestamp):
    "format a long timestamp with microsecond accuracy"
    musecs = ustimestamp % _MILLION
    secs = ustimestamp / _MILLION
    dtf = datetime.datetime.fromtimestamp(secs)
    return dtf.strftime('%Y-%m-%d %H:%M:%S:') + ("%06d" % musecs)
