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

	

