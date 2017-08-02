ZIPPED			:= s3apt.py gnupg.py debian/*


set: requires package

requires:
	pip install -t . -r requirements.txt
	
package:
	zip code.zip $(ZIPPED)