import subprocess
from datetime import datetime
import os

# Create working folder named with TIME_STAMP 
folder='TEST_%s' %( datetime.now().strftime('%Y-%m-%d--%H.%M.%S'))
print folder
cmd1="mkdir %s" %(folder)
subprocess.call(cmd1, shell=True)

#Create a statistics subfolder under our working folder.
cmd3="mkdir ./%s/statistics " %(folder)
subprocess.call(cmd3, shell=True)
print cmd3

# Iteration count of whole simulation
numOfIteration=1

for iter in xrange(numOfIteration):
	print "code started!"
	execfile("flowGenerator_10mb.py")
	print "code Finished!!!"
		
	cmd2="cp -r ./logtxt/ ./%s/_%s/" %(folder,iter)
	#print cmd2	
	subprocess.call(cmd2, shell=True)
	
	
	cmd3="mv statistics* statistics_%s.csv && mv statistics* ./%s/statistics/" %(iter,folder)
    print cmd3
    subprocess.call(cmd3, shell=True)


stat_dir="./%s/statistics/" % (folder)
count=0
for filename in os.listdir(stat_dir):
	if filename.startswith("statistics_"):
		new_name="Sayfa%s.csv" % (count)
		#print filename
		
		
		cmd3="cd ./%s/statistics && pwd && mv %s %s" %(folder,filename,new_name)
		#print cmd3

		subprocess.call(cmd3, shell=True)
		print new_name
		count=count+1
