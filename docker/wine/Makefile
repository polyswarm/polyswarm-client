.DEFAULT_GOAL := context.tar.gz

context.tar.gz: Dockerfile README.md $(wildcard bin/* vendor/libfaudio/*.deb interact/*)
	tar -caf $@ $^
