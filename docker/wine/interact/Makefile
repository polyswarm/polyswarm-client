pkgs = xcb xcb-keysyms xcb-xtest
CFLAGS = `pkg-config --cflags $(pkgs)` -g -Wall
LIBS = `pkg-config --libs $(pkgs)`

interact:	interact.cpp
	$(CXX) $(CFLAGS) interact.cpp $(LIBS) -o interact
