#!/usr/bin/env bash

SOME_IMPORTANT_VARIABLE="foo"

# Start the server in the background
./server.py &

# Keep some high level logic here instead of buried in the python script
if [[ $SOME_IMPORTANT_VARIABLE == "foo" ]]; then
    ./client.py set_thing "bar"
else
    ./client.py set_thing "baz"
fi

# Capture output of an entry point function back out as a variable here:
thing=$(./client.py get_thing)
echo "the bash variable \"thing\" is \"$thing\""

# Make sure to close the server explicitly, or make an entry point function call sys.exit
./client.py exit
