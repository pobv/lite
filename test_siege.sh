#!/bin/sh
# test with siege, should complete within a few minutes

if [ -z "$(which siege)" ]; then
	echo "please install siege to test"
	exit 255
fi


URL=http://localhost/lite # where is lite configured...
CU=20 # number of concurrent users
NRUPDATE=50 # number of update requests per concurrent user
NRREAD=$(expr $NRUPDATE \* 100) # number of read requests per concurrent user

URLUPDATE=$URL/inc
URLREAD=$URL/show

# helper
NRUPDATECU=$(expr $NRUPDATE \* $CU)
get_counter() {
RES=$(sqlite3 data/app.db "SELECT z FROM counter WHERE which = 0")
echo $RES
}


echo "read: ${NRREAD} requests for ${CU} users each, no wait time"
echo "  sqlite with wsgi is fast and scales on read"
./resetapp.sh
LOGFILE=siege_read_${NRREAD}_${CU}.log
echo siege -r ${NRREAD} -c ${CU} -b $URLREAD
siege --log=/dev/null -r ${NRREAD} -c ${CU} -b $URLREAD > $LOGFILE 2>&1 
grep -E "(Elapsed|Concurrency|Longest|rate)" $LOGFILE
echo "done"
sleep 2

echo "update: ${NRUPDATE} requests for ${CU} users each"
echo "  on concurrent update with some sleep time we should do ok"
./resetapp.sh
LOGFILE=siege_${NRUPDATE}_${CU}.log
echo siege -r ${NRUPDATE} -c ${CU} $URLUPDATE
siege --log=/dev/null -r ${NRUPDATE} -c ${CU} $URLUPDATE > $LOGFILE 2>&1 
grep -E "(Elapsed|Concurrency|Longest|rate)" $LOGFILE
echo "expected $NRUPDATECU got" $(get_counter)
sleep 2


# you may want to check error.log to see timeouts, 
# on my machine /var/log/apache2/error.log
echo ""
echo "update: ${NRUPDATE} requests for ${CU} users each (no wait time)"
echo "  obviously, it is not fast nor scales on update/write"
./resetapp.sh
LOGFILE=siege_${NRUPDATE}_${CU}_battle.log
echo siege -r ${NRUPDATE} -c ${CU} -b $URLUPDATE > $LOGFILE 2>&1
siege --log=/dev/null -r ${NRUPDATE} -c ${CU} -b $URLUPDATE > $LOGFILE 2>&1
grep -E "(Elapsed|Concurrency|Longest|rate)" $LOGFILE
echo "expected $NRUPDATECU got" $(get_counter)
