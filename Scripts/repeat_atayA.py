import subprocess
from datetime import datetime
import os
import MySQLdb


repeat=3

folder='TEST_%s' %( datetime.now().strftime('%Y-%m-%d--%H.%M.%S'))
print folder
cmd1="mkdir ./%s/ && mkdir ./%s/statistics" %(folder,folder)

subprocess.call(cmd1, shell=True)
db = MySQLdb.connect(host="localhost",  # your host, usually localhost
                   user="root",  # your username
                   passwd="1234",  # your password
                   db="POLICYDB")  # name of the data base



routing=['HQoS','MinHop']
#routing=['HQoS']

for it in xrange(len(routing)):

	sql_request_simulation="UPDATE Simulation set var1='%s' where SimulID=1;" % (routing[it])
	cur = db.cursor()
	cur.execute(sql_request_simulation)


	for iter in xrange(repeat):
        	
		print "----REPEAT %s -------" %(iter)

		cmd_clean="kill -9 `pidof ITGRecv`"
		print cmd_clean	
		subprocess.call(cmd_clean, shell=True)
	
		cmd_clean2="kill -9 `pidof ITGSend`"
		print cmd_clean2
		subprocess.call(cmd_clean2, shell=True)

	
		print "code started!"
		execfile("flowGenerator_atay_10m_a.py")
		
		time.sleep(60)
		# log -> logtxt DiTGDec works!
		execfile("ditgDec.py")
		print 'txt conversion completed!'

		time.sleep(5)
		#/logtxt outputs parsed into statistics_{date}.csv
		execfile("excel.py")
		print 'Statistic.csv is created!'
		print "Good bye!"
		print "code Finished!!!"
	
		#readable /logtxtler _0_{routing} foldera tasiniyor
		cmd2="cp -r ./logtxt/ ./%s/_%s_%s/" %(folder,iter,routing[it])

		print cmd2
	
		subprocess.call(cmd2, shell=True)

                #cmd2a="cd ./%s/statistics && mv statistics* Sayfa_%s_%s.csv" %(folder,iter,routing[it])
                cmd2a="mv statistics* ./%s/statistics/Sayfa_%s_%s.csv" %(folder,iter,routing[it])
                print cmd2a

                subprocess.call(cmd2a, shell=True)

	
	
