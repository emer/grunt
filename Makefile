# grund commands for initial configuration and server-side

link: 
	@echo "Making a link to grunt.py as grunt in ~/bin"
	ln -s `pwd`/grunt.py $(HOME)/bin/grunt

reset:
	python3 grunt.py reset

server:
	nohup python3 grund.py &
	
tail:
	tail -f nohup.out

	
# NOTE: MUST update version number here prior to running 'make release'
VERS=v1.0.3
PACKAGE=grunt
GIT_COMMIT=`git rev-parse --short HEAD`
VERS_DATE=`date -u +%Y-%m-%d\ %H:%M`
VERS_FILE=version.go

release:
	/bin/rm -f $(VERS_FILE)
	@echo "// WARNING: auto-generated by Makefile release target -- run 'make release' to update" > $(VERS_FILE)
	@echo "" >> $(VERS_FILE)
	@echo "package $(PACKAGE)" >> $(VERS_FILE)
	@echo "" >> $(VERS_FILE)
	@echo "const (" >> $(VERS_FILE)
	@echo "	Version     = \"$(VERS)\"" >> $(VERS_FILE)
	@echo "	GitCommit   = \"$(GIT_COMMIT)\" // the commit JUST BEFORE the release" >> $(VERS_FILE)
	@echo "	VersionDate = \"$(VERS_DATE)\" // UTC" >> $(VERS_FILE)
	@echo ")" >> $(VERS_FILE)
	@echo "" >> $(VERS_FILE)
	/bin/cat $(VERS_FILE)
	git commit -am "$(VERS) release -- $(VERS_FILE) updated"
	git tag -a $(VERS) -m "$(VERS) release"
	git push
	git push origin --tags

