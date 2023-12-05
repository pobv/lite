# lite

Collection of some best practices using sqlite3 (https://www.sqlite.org/)
and python (https://www.python.org/) in a  Web application 
with WSGI (http://legacy.python.org/dev/peps/pep-3333/).
Main target is mod_wsgi (https://code.google.com/p/modwsgi/)
and apache (http://httpd.apache.org/)
with multiprocessing, threading is supported as well.


`lite` is a simple `app` concurrently modifying a single counter which
is stored in a sqlite database. 
We update that counter concurrently without failure as long as there are no
(socket) timeouts from apache.
In addition, a config file is safely applied whenever its file modification time 
changes concurrently. 
The counter value is overwritten which means the value of the counter at the end
of a concurrent inc test if no longer predictable.
To test for yourself copy (and adapt) `lite.conf` to the place where your 
apache config files live and activate it.
Run `./resetapp.sh` once.
Go to `http://localhost/lite` or whereever you put it and play with
what you can do manually. 
However, interesting are some simple load tests.
If you have `siege` installed, test it with `./test_siege.sh`.
It should scale with a couple of thousand read requests per second.
On the following two concurrent update tests performance drops to a few dozen writes
per second if at all but safe unless apache gives up.
All that just as a reminder to myself and anybody finding it useful.
No licence, public domain.


sqlite3 is a brilliant database for fast read, but not as good and not 
intended for heavy concurrent write. 
Although it is ok for the infrastructure to slow down and not scale 
under heavy load, it should still behave correctly ... and then we 
may enter "sqlite3.OperationalError, database is locked" nightmare
(http://beets.radbox.org/blog/sqlite-nightmare.html,
 http://stackoverflow.com/questions/5529820/sqlite3-operationalerror-database-is-locked,
 http://stackoverflow.com/questions/3172929/operationalerror-database-is-locked,
 http://stackoverflow.com/questions/2569233/sqlite3-operationalerror-database-is-locked-non-threaded-application,
 ...), 
which we want to avoid with `db.py`.
We open the database and keep it open, one open connection per thread/process in 
the db module. 
We use thread locals which work both in process and threading environments (in a 
process environment we just have one thread).
Every database interaction, at least every request, runs in its own 
newly created cursor, which is always closed after usage 
(even if that does not seem to be strictly necessary according to python sqlite documentation). 
With `transact`, `transact_one`, `transact_many` functions, one can execute
statements that modify the database in a transaction context. 
On failure we *catch* the exception and indicate failure by returning False
for modifications and None for reads.
There is a `get` to read single attributes from a table row identified by a single
primary key.
There is an `upsert`, which may come in handy.
Do not misuse upsert for a read, modify, write cycle as this is not safe 
(it introduces a race condition).
See the `app` module for how to read, modify, write.
There, we concurrently increment a counter.

To test everything we use `siege`. Three different tests are run with 
`./test_siege.sh`
First, we use the database as content provider and only read by simulating
20 users hitting 5000 times each as fast as possible an url retrieving 
the counter value. 
That yields on my machine (i7-2600, 256 GB SSD) with around 20 apache processes
more than 10000 requests per second. Fast and scalable.
Then, we concurrently let these 20 users increment that counter 50 times each
introducing concurrent load, but with wait time. 
That should still work find and we should not experience and problems (check the log).
After around half a minute we should be done.
Third, we try to bring it down by letting the 20 users do the concurrent increment
50 times again, but that time  without any wait time as fast as possible.
We introduce heavy concurrent load. Although the apache log should fill up with
lots of weird error messages we should at the end come out with the value 1000
as all operational errors (database locked) should be covered. 
In case apache chokes we will see failed transactions in the siege log and obviously
these increments are then lost.
On heavy concurrent load it really becomes slow compared to read, on my machine still
around 80 transactions per second, but that can be much lower on slower non-SSD infrastructure.
But hey, heavy concurrent write constitutes a severe misuse of sqlite; 
but it still works...


As sqlite is used most often as database to deliver content even under heavy load,
it behaves often like a cache. 
The content of a cache does not change for some time, but then it needs to be updated. 
This happens, for example, whenever a configuration file changes. 
That pattern is safely implemented in `config` with the file `config.ini`. 
Whenever a config file changes the database is updated exactly *once* by one of the 
python processes locking out other processes that try to update it as well. 
The goal is to eventually (not necessarily immediately [whatever that means]) reach a state 
where the database has the new values based on the configuration. 
We configure in the example two counters in `config.ini` of which we increment one counter 
in the load test.
Touching the `config.ini` during modification resets the counter and should (of course) 
give different results at the end under load. 
Note that a typical application in which `config.ini` changes is not concurrent update such
as counting, but e.g. refreshing a content database.
In such a setting the update should work smoothly.

Have fun
