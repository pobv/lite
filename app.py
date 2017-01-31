"main application, no web stuff"

import db

db.set_dbpath("data/app.db")


# application
def get_counter(which=0):
    "get value from counter which"
    return db.get('counter', 'which', which, 'z')

_INC_UPDATE = "UPDATE counter SET z = z+1 WHERE which = ?"
def inc_counter(which=0):
    "transactionally safe increment of counter which"
    # try until it works
    try:
        # note, cannot use upsert, as there would be a race
        while not db.transact_one(_INC_UPDATE, [which]):
            pass
        return True
    except Exception as data:
        db.log_error("inc_counter %d" % which, data)
        return False

def set_counter(which=0, zval=0):
    """transactionally safe set of counter which to z,
    creates entry if not available"""
    db.upsert('counter', 'which', which, 'z', zval)

