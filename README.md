# Stateful Python

This server/client model uses a local unix socket to allow for the client script to request the server to run any function inside the server script decorated with the `SERVER_ENTRY_POINT` decorator.

All stdout and stderr are sent back to the client for it to display (and optionally be captured as a variable by a parent shell script calling the client, etc.).
The server stays running until explicitly asked to exit or if an error occurs.

The idea is that you can more easily see high level logic of steps in something like a GitLab cicd yaml file or a shell script
as if they were separate processes, but since this server script runs continuously in the background, you can maintain state in the python script.

See [example.sh](./example.sh)
