# lite

Collection of some best practices using sqlite3 and python in 
a web application with wsgi 
(main target mod_wsgi/apache with multiprocess=True, no threading).
We do a simple app concurrently modifying a single counter which
is stored in the database and hammer on it concurrently without failure.
A config file is applied whenever its file modification time changes
concurrently to reads (and update as well but what does that mean...)
and safely applied.
Copy (and adapt) lite.conf where you store your apache config files 
and activate it.
Run ./resetapp.sh once.
Go to http://localhost/lite or whereever you put it and play with
what you can do manually. 
However, interesting are simple load tests.
If you have siege installed, test it with ./test_siege.sh.
All that just as a reminder to myself and anybody finding it useful.
No licence, public domain.


sqlite3 is a brilliant database for fast read, but not for 
heavy concurrent write. 
Although it is ok for the infrastructure to slow down and not scale 
under heavy load, it should still behave correctly ... and then we 
enter "OperationalError, database locked" nightmare, which we want to 
avoid with db.py.
We open the database and keep them open per module. 
Every db interaction, at least every request, runs in its newly created cursor
which is always closed after usage (even if that does not seem to be strictly
necessary). 
With transact, transact_one, transact_many statements that modify the database
can be executed in a transaction context. 
On failure we *catch* the exception and indicate failure by returning False
for modifications and None for reads.
There is a get to read single attributes from a table row identified by a single
primary key.
There is an upsert, which may come in handy from time to time.
Do not misuse upsert for a read, modify, write cycle as this would introduce 
a race.
See the app module for how to read, modify, write.
There, we concurrently increment a counter.

To test everything we use siege. Three different tests are run with 
$./test_siege.sh
First, we use the database as content provider and read only by simulating
20 users hitting 5000 times each as fast as possible an url retrieving 
the counter value. 
That yields on my machine (i7-2600, 256 GB SSD) with around 20 apache processes
> 10000 requests per second. Fast and scalable.
Then, we concurrently let these 20 users increment that counter 50 times each
introducing concurrent load, but with wait time. 
That should still work find and we should not experience and problems (check the log).
After half a minute we should be done.
Third, we try to bring it down by letting the 20 users do the concurrent increment
50 times again, but that time  without any wait time as fast as possible.
We introduce heavy concurrent load. Although the apache log should fill up with
lots of weird error messages we should at the end come out with the value 1000
as all operational errors (database locked) should be covered. 
Now it really becomes slow compared to read, on my machine 80 transactions per second.
But hey, it is a misuse and it still works...


As sqlite is used most often as database to deliver content even under heavy load,
it behaves often like a cache. 
A cache stays the same for a long time, but sometimgs you want to update or modify it. 
Most simply, whenever a configuration file changes. 
That pattern is safely implemented in config with the file config.ini. 
Whenever a config file changes the database is updated exactly *once* by one of the 
python processes locking out other processes that try to update it as well. 
Goal is to eventually (not necessarily immediately [whatever that means]) reach a state 
where the database has the new values based on the configuration. 
We configure in the example two counters in config.ini of which we increment one counter 
in the load test.
Touching the config.ini during modification resets the counter and should (of course) 
give different results at the end under load. 
Note that a typical application for that config.ini changing is not counting, but e.g. 
refreshing a content database.

Have fun
