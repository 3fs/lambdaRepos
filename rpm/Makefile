ZIPPED			:= s3rpm.py gnupg.py pyrpm/* pyrpm/tools/*


set: requires package

requires:
	pip3 install -t . -r requirements.txt --upgrade
	
package:
	zip code.zip $(ZIPPED)
