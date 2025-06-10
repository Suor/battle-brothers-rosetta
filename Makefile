MOD_NAME = rosetta
TAG_NAME =''
SOURCES = rosetta scripts

include .env
export
SHELL := /bin/bash

.ONESHELL:
test: check-compile
	@set -e;
	TMP_FILE=$$(mktemp);
	squirrel test.nut 2> >(tee "$$TMP_FILE" >&2);
	if [ -s "$$TMP_FILE" ]; then
		rm "$$TMP_FILE"
		exit 1
	fi

zip: test
	@set -e;
	LAST_TAG=$$(git tag | grep $(TAG_NAME) | tail -1);
	echo $$LAST_TAG;
	MODIFIED=$$( git diff $$LAST_TAG --quiet $(SOURCES) || echo _MODIFIED);
	FILENAME=mod_$(MOD_NAME)_$${LAST_TAG}$${MODIFIED}.zip;
	zip --filesync -r "$${FILENAME}" $(SOURCES);

clean:
	@rm -f *_MODIFIED.zip;

install: test
	@set -e;
	FILENAME=$(DATA_DIR)mod_$(MOD_NAME)_TMP.zip;
	zip --filesync -r "$${FILENAME}" $(SOURCES);

check-compile:
	@set -e
	find . -name \*.nut -print0 | xargs -0 -n1 squirrel -c && echo "Syntax OK"
	rm out.cnut
