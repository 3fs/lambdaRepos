ZIPPED			:= s3rpm.py gnupg.py pyrpm/* pyrpm/tools/*


set: requires compress

requires:
	pip3 install -t . -r requirements.txt
	
compress:
	zip code.zip $(ZIPPED)