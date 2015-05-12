"""database access layer for sqlite3
can be run from several processes as well as from several
threads in a process within wsgi setup in apache
"""

import sqlite3
import contextlib # for closing
import threading # threadlocal connections


# overwrite with something sensible (done by app module)
DATABASE_FILE = ":memory:"

# each thread in each process uses its own single connection
_CON = threading.local()

def set_dbpath(pathname):
    """sets up the file to the sqlite database, must be writeable and
    in a writeable directory"""
    global DATABASE_FILE, _CON
    DATABASE_FILE = pathname
    # cannot close open db connections, no way to be in all threads
    # just discard. Hopefully, nobody opens db connections and then
    # resets the db_path. In that case there might be leaking db
    # connections in remaining threads
    _CON = threading.local() # new local store

def _connect():
    "sets up a globally available connection (per thread) and returns it"
    try:
        if getattr(_CON, "con", None):
            try:
                _CON.con.close()
            except Exception, data:
                log_warn("_connect: try to close connection")
                # ignore
        _CON.con = sqlite3.connect(DATABASE_FILE)
        _CON.con.row_factory = sqlite3.Row
        _CON.con.execute("PRAGMA foreign_keys = ON")
        return _CON.con
    except sqlite3.Error, err:
        log_error("_connect", err)
        return None

def get_cursor(fail=True):
    """creates and returns a cursor that can be safely used within a
    with statement. The cursor will be closed at the end of the with.
    If there is no connection yet, create one. """
    if getattr(_CON, "con", None) == None:
        _connect()
    if getattr(_CON, "con", None) == None and fail:
        raise Exception("No database connection for %s" % DATABASE_FILE)
    return contextlib.closing(_CON.con.cursor()) # close cursor after using it


def transact(func):
    """execute a function, thus all database interactions in that function,
    within a transaction; rollbacks if necessary, True iff success. Do
    not use transaction in the statements in that function"""
    with get_cursor() as cur:
        try:
            cur.execute("BEGIN")
            func(cur)
            cur.connection.commit()
            return True
        except Exception, data:
            cur.connection.rollback()
            msg = u"transact func=%s, %s"
            log_error(msg % (func.__name__, func.__doc__), data)
            return False

def transact_one(statement, params):
    "execute a single statement within a transaction, True iff success"
    def doit(cur):
        cur.execute(statement, params)
    doit.__doc__ = "execute %s %s" % (statement, str(params))
    doit.__name__ = "transact_one"
    return transact(doit)

def transact_many(statements):
    "execute a series of statements with transact, True iff success"
    def doit(cur):        
        for statement, params in statements:
            cur.execute(statement, params)
    # ldoc = ["exec(%s, %s)" % (s, p) for (s, p) in statements]
    # doit.__doc__ = "\n  ".join(ldoc)
    doit.__doc__ = "execute %d statements" % len(statements)
    doit.__name__ = "transact_many"
    return transact(doit)


# upsert, update or insert
# First, update or ignore, then insert or ignore
# Thus, if update succeeds, done and insert silently fails
# otherwise update silently fails and insert will do the job
_UPDATEORIGNORE = u"""UPDATE OR IGNORE %(table)s
  SET %(attr)s = ? WHERE %(key)s = ?"""
_INSERTORIGNORE = u"""INSERT OR IGNORE INTO %(table)s(%(key)s, %(attr)s)
  VALUES (?, ?)"""
def upsert(table, key, keyval, attr, attrval):
    """upsert in a table one attribute of a row identified by a key,
    True iff success"""
    dic = {'table': table, 'key': key, 'attr': attr}
    with get_cursor() as cur:
        try:
            cur.execute("BEGIN")
            updateign = _UPDATEORIGNORE % dic
            cur.execute(updateign, [attrval, keyval])
            insertign = _INSERTORIGNORE % dic
            cur.execute(insertign, [keyval, attrval])
            cur.connection.commit()
            return True
        except Exception, data:
            log_error("upsert %s -> rolling back" % updateign, data)
            cur.connection.rollback()
            return False


_SELECT = u"""SELECT %(attr)s FROM %(table)s WHERE %(key)s = ?"""
def get(table, key, keyval, attr):
    """retrieves of a table one value of an attribute from one row
    identified by a key, None if not existing."""
    with get_cursor() as cur:
        try:
            sql = _SELECT % {'table': table, 'key': key, 'attr': attr}
            cur.execute(sql, [keyval])
            return one_or_none(cur)
        except sqlite3.OperationalError, data: # unlikely, but hey
            log_error("get %s, %s -> None" % (sql, str(keyval)), data)
            return None

def one_or_none(cur):
    "one value or none"
    one = cur.fetchone()
    if one:
        return one[0]
    return None

def _log_level(msg, data, level):
    "dump to apache error log"
    if data != None:
        msg = "%s: %s: %s, %s" % (level, msg, str(type(data)), str(data))
    else:
        msg = "%s: %s:" % (level, msg)
    print(msg)

def log_warn(msg, data=None):
    "log warning onto apache log"
    _log_level(msg, data, "Warn")

def log_error(msg, data=None):
    "log error onto apache log"
    _log_level(msg, data, "Err ")
