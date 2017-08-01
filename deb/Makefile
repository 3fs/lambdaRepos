ZIPPED			:= s3apt.py gnupg.py debian/*


all: requires compress

requires:
	pip install -t . -r requirements.txt
	
compress:
	zip code.zip $(ZIPPED)