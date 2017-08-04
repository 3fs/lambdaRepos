ZIPPED			:= s3rpm.py gnupg.py pyrpm/* pyrpm/tools/*


set: requires compress

requires:
	pip3 install -t . -r requirements.txt --upgrade
	
compress:
	zip code.zip $(ZIPPED)

coverage:
	coverage run s3rpm_test.py
	coverage html
	open htmlcov/index.html