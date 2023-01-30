#!/usr/bin/env bash



# Start the server in the background
./server.py &

# Now you run functions inside of server.py by calling client.py with the name of the function and any args you want to pass to it
# ./client.py name_of_an_entry_function arg1 arg2 arg3 ... argn


# You can keep some high level logic here instead of buried in the python script for improved readability
SOME_IMPORTANT_VARIABLE="foo"

if [[ $SOME_IMPORTANT_VARIABLE == "foo" ]]; then
    ./client.py set_thing "bar"
else
    ./client.py set_thing "baz"
fi


# Capture output of a function back out as a variable here:
thing=$(./client.py get_thing)
echo "the bash variable \"thing\" is \"$thing\""


# Every time the client requests a function from the server, the server's env is updated to match the clients
export foo=one
./client.py print_env_var_foo

export foo=two
./client.py print_env_var_foo

export foo=three
./client.py print_env_var_foo


# Make sure to close the server explicitly, or make an entry point function call sys.exit
./client.py exit


./server.py &

# If you try to call a function in server.py that hasn't been marked as an entry point function it will throw an error
./client.py function_that_isnt_valid
