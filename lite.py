"the main application (and web user interface)"

import wsgiref.util
import codecs

import app
import config


CHECK_CONFIG = True # check whether config update is needed
CONFIGPATH = "config.ini" # if we need to get that from the db
    # it will be tough during load...

# read templates once per python process, templates do not change
# and global scope is ok as cache
with codecs.open('page.tpl', 'r', encoding='utf8') as f:
    PAGE = f.read()


LITE = "/lite"
def application(environ, start_response):
    "the apache mod_wsgi entry point, central dispatcher"
    if CHECK_CONFIG:
        # reading the configpath globally is a bad idea
        # new processes are added if there is database contention
        # but exactly then reading from the database fails...
        # use a default if available
        configpath = CONFIGPATH if CONFIGPATH else config.get_configpath()
        if configpath:
            config.update_config(configpath)
    reqpath = _request_path(environ)
    content = []
    if reqpath.startswith(LITE):
        reqpath = reqpath[len(LITE):]
    if reqpath == "/" or reqpath.startswith("/index"):
        index(environ, content)
    elif reqpath.startswith("/show"):
        show(environ, content)
    elif reqpath.startswith("/inc"):
        inc(environ, content)
    elif reqpath.startswith("/init"):
        init(environ, content)
    elif reqpath.startswith("/env"):
        env(environ, content)
    else:
        content.append(u"%s WHAT?" % reqpath)
    content = PAGE % {'title': u"python and sqlite3 patterns and tests",
                      'content': u"\n".join(content),
                      'home': wsgiref.util.application_uri(environ)
                      }
    content = content.encode('utf-8')
    start_response('200 OK', [
        ('Content-Type', "text/html; charset=utf-8"),
        ('Content-Length', str(len(content)))
        ])
    return [content]


# one function per functionality as dispatch endpoint

def index(environ, content):
    "entry"
    basepath = wsgiref.util.application_uri(environ)
    if basepath.endswith("/"):
        basepath = basepath[:-1]
    content.append(u"""
    /: this page <br />
    <a href="%(base)s/show">show</a>: show counter <br />
    <a href="%(base)s/inc">inc</a>:
    increment counter and show result
    (transactionally safe, may fail) <br />
    <a href="%(base)s/init">init</a>: initialize counter to default settings
    from config file <br />
    <a href="%(base)s/env">env</a>: show the environment (admin) <br /><br />
    
    <form name="postincform" method="POST" action="%(base)s/inc">
    Do a POST request to
    <a href="javascript:document.postincform.submit()">inc</a>.
    </form>
    <form name="postinitform" method="POST" action="%(base)s/init">
    Do a POST request to 
    <a href="javascript:document.postinitform.submit()">init</a>.
    </form>

    <h3> To test concurrency do </h3>
    <tt> $ ./resetapp.sh </tt> <br />
    which initializes the database, followed by <br />
    <tt> $ siege -r 50 -c 20 http://localhost/lite/inc
    </tt> <br />
    Then siege does a load test with 20 users each doing 50 requests
    of concurrently incrementing the same counter (0).
    By adding <tt>-b</tt> to battle [no wait time between requests] it is
    likely to experience timeout errors (look at the apacher error log).
    We handle a timeout error in the app by redoing.
    Thus, we force the update until apache gives up.
    If apache hangs on we should always have incremented the counter
    by 1000 at the end - all being transactionally safe.
    <h3> To test intermittent config reload do </h3>
    <p> just another siege, maybe a little bit longer with
    <tt>-r 200 </tt> and add <tt> -b </tt> as well giving <br />
    <tt> $ siege -r 200 -c 20 -b http://localhost/lite/inc
    </tt> <br />
    but during load test click on
    <a href="%(base)s/init">init</a>
    to initialize the counters from the config file.
    Obviously, you cannot expect 4000 as result but any number
    less than 4000.
    </p>
    <p> Alternatively, touch the config.ini file.
    It will be reloaded exactly once (check the apache error log)
    and again a number less than 4000 will come up.
    </p>
    """ % {'base': basepath})

def show(_, content):
    "show the counter"
    counter = app.get_counter()
    if counter == None:
        content.append("counter is None, rare lockout")
        return
    content.append(u"counter = %d" % counter)

def inc(environ, content):
    "increment the counter"
    _statewarn(environ, content)
    if app.inc_counter():
        content.append(u"counter incremented <br />")
    else:
        content.append(u"counter not incremented <br />")
    show(environ, content)

def env(environ, content):
    "show the environment (debugging/tracing)"
    configpath = config.get_configpath()
    ctimef = config.get_modified_configpath_fs(configpath)
    sctimef = config.fmt_ts(ctimef) if ctimef else "None"
    ctimeu = config.get_modified_configpath_db(configpath)
    sctimeu = config.fmt_ts(ctimeu) if ctimeu else "never"
    content.append(u"""<table>
    <tr><td>%s</td><td>%s</td></tr>
    <tr><td>%s</td><td>%s</td></tr>
    <tr><td>%s</td><td>%s</td></tr>
    </table>""" % ("configpath", configpath,
                   "modified", sctimef,
                   "modified of read", sctimeu))
    content.append(u"<br /><strong>contents of %s </strong><br />" % configpath)
    for entry in config.read_config(configpath):
        content.append(str(entry) + "<br />")
    content.append(u"<br /> <br /><strong>environ</strong>")
    # the most important ones first
    important = ("wsgi.multithread", "wsgi.multiprocess")
    for key in important:
        content.append(_envvar(environ, key))
    # everything else
    for key in environ:
        if key not in important:
            content.append(_envvar(environ, key))


def init(environ, content):
    "initialize the environment by applying a configuration file once"
    _statewarn(environ, content)
    if config.apply_config(config.get_configpath()):
        content.append(u"initialized <br />")
    else:
        content.append(u"not initialized <br />")
    show(environ, content)



# some helpers

def _envvar(environ, key):
    "show an environment variable"
    msg = u"<br /> %(key)s: %(value)s"
    value = str(environ[key])
    return msg % {'key': key, 'value':value}

def _statewarn(environ, content):
    "warn if method is not suitable for state change"
    if _method(environ) not in ("POST", "PUT"):
        msg = u"You may prefer doing a POST request for changing state <br />"
        content.append(msg)

def _method(environ):
    "which HTTP method is it"
    return environ['REQUEST_METHOD'].upper()

def _request_path(environ):
    "application specific path"
    base_path = wsgiref.util.application_uri(environ)
    complete_path = wsgiref.util.request_uri(environ)
    if not complete_path.startswith(base_path):
        raise Exception("complete_path %s\ndoes not start with base_path %s",
                        complete_path, base_path)
    ret = complete_path[len(base_path):]
    if not ret.startswith("/"):
        ret = "/"+ret
    return ret


# for local development (only)

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    HTTPD = make_server('', 8000, application)
    print "Serving HTTP on port 8000, press Ctrl-C to exit..."
    print "... and better run it under apache to test and benchmark"
    HTTPD.serve_forever()
