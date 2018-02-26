import os
filenames=os.listdir("./log")
for file in filenames:

	bashcmd='/home/ubuntu/D-ITG/bin/ITGDec ./log/%s > ./logtxt/%s' % (file,file)
	os.system(bashcmd)
	