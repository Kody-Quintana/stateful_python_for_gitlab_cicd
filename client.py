#!/usr/bin/env python3

"""
This client requests the server to run a function matching the name of the first argument to this script,
the rest of the command line arguments are sent as arguments to that requested function in the server.
The server's env is updated to match the env of this client when this client makes a request.

While that function runs in the server, any stdout and stderr messages are sent back to this client to be displayed.
When the function returns in the server, this client exits.
"""

import socket
import time
import json
import sys
import os


SOCKET_NAME = "./stateful-python-coordinator-socket"


class ClientEntryPoints():
    """Instantiate this class, then use that instance as a decorator for any functions that are to be used as an entry point."""
    def __init__(self):
        self.valid_entry_points = {}

    def __call__(self, func):
        self.valid_entry_points.update({func.__name__: func})
        return func

    def run(self, func_name, args):
        """Ensure a function being requested by the server has been tagged (decorated) as a valid entry point"""
        if func_name in self.valid_entry_points:
            self.valid_entry_points[func_name](*args)
        else:
            print(f"Error {func_name} not in valid entry points", file=sys.stderr)
            sys.exit(1)


CLIENT_ENTRY_POINT = ClientEntryPoints()


@CLIENT_ENTRY_POINT
def print_server_stdout(text):
    """Display messages from the server"""
    print(text, end='', file=sys.stdout)


@CLIENT_ENTRY_POINT
def print_server_stderr(text):
    """Display errors from the server"""
    print(text, end='', file=sys.stderr)


@CLIENT_ENTRY_POINT
def _exit(exit_code):
    """Named _exit to avoid redefining builtin"""
    sys.exit(exit_code)


def main():  # pylint: disable=missing-function-docstring
    if len(sys.argv) < 2:
        print("Argument required")
        sys.exit(1)

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        try:

            # Connect to local unix socket
            connection_attempts = 0
            while True:
                try:
                    client.connect(SOCKET_NAME)
                    break
                except (ConnectionRefusedError, FileNotFoundError):
                    connection_attempts += 1
                    if connection_attempts < 10:
                        print(f"[{os.path.basename(__file__)}]: Waiting for {SOCKET_NAME}")
                        time.sleep(connection_attempts * 0.1)
                        continue
                    print(f"[{os.path.basename(__file__)}]: Couldn't connect after {connection_attempts} attempts", file=sys.stderr)
                    sys.exit(1)

            # Send argv as a json payload to the server.
            # Note the trailing newline, that is there so we can use readline() in the server
            client.sendall((json.dumps({
                "function_name": sys.argv[1],
                "args": [] if len(sys.argv) < 2 else sys.argv[2:],
                "env": dict(os.environ)
            }) + "\n").encode('utf-8'))

            # Continue reading from the server until _exit is requested from the server
            bufsize = 131072
            json_decoder = json.JSONDecoder()
            while True:
                message_from_server = client.recv(bufsize).strip().decode('utf-8')
                if message_from_server:
                    try:
                        # Client may receive several json strings concatenated into one
                        # so here we use raw_decode to iterate over the json strings
                        msg_pos, msg_last = 0, len(message_from_server) - 1
                        while msg_pos < msg_last:
                            request_from_server, msg_pos = json_decoder.raw_decode(message_from_server, msg_pos)

                            CLIENT_ENTRY_POINT.run(*[request_from_server[x] for x in ["function_name", "args"]])

                    except json.decoder.JSONDecodeError as exception:
                        print(exception)
        finally:
            client.close()


if __name__ == "__main__":
    main()
