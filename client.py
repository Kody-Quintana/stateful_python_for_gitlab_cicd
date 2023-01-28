#!/usr/bin/env python3

import socket
import json
import sys

SOCKET_NAME = "/tmp/test"


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
    for line in text.split("\n"):
        print(f"[Daemon msg]: {line}", file=sys.stdout)


@CLIENT_ENTRY_POINT
def print_server_stderr(text):
    """Display errors from the server"""
    for line in text.split("\n"):
        print(f"[Daemon err]: {line}", file=sys.stderr)


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
            client.connect(SOCKET_NAME)

            # Note the trailing newline, that is there so we can use readline() in the server
            client.sendall((json.dumps({
                "function": sys.argv[1],
                "args": [] if len(sys.argv) < 2 else sys.argv[2:]
            }) + "\n").encode('utf-8'))

            bufsize = 131072
            while True:
                message_from_server = client.recv(bufsize).strip().decode('utf-8')
                if message_from_server:
                    try:
                        # Client may receive several json strings concatenated into one
                        # so here we use raw_decode to iterate over the json strings
                        msg_index, msg_length = 0, len(message_from_server) - 1
                        while msg_index < msg_length:
                            msg_object, msg_index = json.JSONDecoder().raw_decode(message_from_server, msg_index)

                            CLIENT_ENTRY_POINT.run(*[msg_object.get(x) for x in ["function", "args"]])

                    except json.decoder.JSONDecodeError as exception:
                        print(exception)
        finally:
            client.close()


if __name__ == "__main__":
    main()
