DROP TABLE IF EXISTS admin;
DROP TABLE IF EXISTS counter;

-- the application data, in this case just some counters
CREATE TABLE counter (
	   which INTEGER PRIMARY KEY,
	   z INTEGER
);
-- initialization will be done by the python module 
-- challenge: will be to do it just *once*
INSERT INTO counter VALUES(0, 0);
INSERT INTO counter VALUES(42, 17);



-- the admin portion, used to ensure loading once
CREATE TABLE admin (
	   configpath TEXT PRIMARY KEY, -- from which config file
	   modified TEXT -- timestamp, modification date of config file loaded
                     -- (TEXT, never trust REAL, we use microseconds here)
);
-- insert exactly one config file and keep that entry 
-- but modify its updated and uuid attributes to communicate 
-- between processes (blackboard)
INSERT INTO admin VALUES ('config.ini', NULL);
