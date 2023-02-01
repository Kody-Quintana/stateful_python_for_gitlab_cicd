#!/usr/bin/env python3

"""
This script creates a local unix socket to allow for a client script to request the server to run any function decorated with the SERVER_ENTRY_POINT decorator.
All stdout and stderr are sent back to the client for it to display.
This script (the server) stays running until explicitly asked to exit or if an error occurs.

The idea is that you can more easily see high level logic of steps in something like a GitLab cicd yaml file or a shell script
as if they were separate processes, but since this server script runs continuously in the background, you can maintain state in the python script.
"""

from socketserver import UnixStreamServer, StreamRequestHandler
from textwrap import dedent
from inspect import signature
import traceback
import json
import stat
import sys
import os


SOCKET_NAME = "./stateful-python-coordinator-socket"


class ServerEntryPoints():
    """Instantiate this class, then use that instance as a decorator for any functions that are to be used as an entry point."""
    def __init__(self):
        self._valid_entry_points = {}

    def __call__(self, func):
        """This is called when an instance of this class is used as a decorator"""
        self._valid_entry_points.update({func.__name__: func})
        return func

    def run(self, func_name, args):
        """Ensure a function being requested by the client has been tagged (decorated) as a valid entry point"""
        if func_name in self._valid_entry_points:
            return self._valid_entry_points[func_name](*args)
        error_message = dedent(f'''\
            "{func_name}" is not a valid entry point function in {os.path.basename(__file__)}

            Remember to first decorate those functions with @SERVER_ENTRY_POINT like this:

            @SERVER_ENTRY_POINT
            def my_entry_point():
                do something here...

            Current valid entry points are:
            ''') + '\n'.join(f"  • {x[0]}{signature(x[1])}" for x in self._valid_entry_points.items())
        raise NameError(error_message)


# Only instantiate this once
SERVER_ENTRY_POINT = ServerEntryPoints()


#   ____  ______ _____ _____ _   _     ______ _   _ _______ _______     __    _____   ____ _____ _   _ _______ _____
#  |  _ \|  ____/ ____|_   _| \ | |   |  ____| \ | |__   __|  __ \ \   / /   |  __ \ / __ \_   _| \ | |__   __/ ____|
#  | |_) | |__ | |  __  | | |  \| |   | |__  |  \| |  | |  | |__) \ \_/ /    | |__) | |  | || | |  \| |  | | | (___
#  |  _ <|  __|| | |_ | | | | . ` |   |  __| | . ` |  | |  |  _  / \   /     |  ___/| |  | || | | . ` |  | |  \___ \
#  | |_) | |___| |__| |_| |_| |\  |   | |____| |\  |  | |  | | \ \  | |      | |    | |__| || |_| |\  |  | |  ____) |
#  |____/|______\_____|_____|_| \_|   |______|_| \_|  |_|  |_|  \_\ |_|      |_|     \____/_____|_| \_|  |_| |_____/
#


@SERVER_ENTRY_POINT
def set_thing(value):
    """example entry point where we create a global"""
    globals()['THING'] = value
    print(f"global variable THING is now \"{THING}\"")  # noqa  pylint: disable=undefined-variable


@SERVER_ENTRY_POINT
def get_thing():
    """another example entry point where we read the new global from the first example"""
    print(THING)  # noqa  pylint: disable=undefined-variable


@SERVER_ENTRY_POINT
def print_env_var_foo():
    """Example entry point to show that the client updates the server with its env every call"""
    print(os.environ.get("foo"))


@SERVER_ENTRY_POINT
def exit(exit_code=0):  # pylint: disable=redefined-builtin
    """sys.exit can be used in any entry point function.
    A clean shutdown will be handled by catching the SystemExit exception."""
    sys.exit(exit_code)


#   ______ _   _ _____      ______ _   _ _______ _______     __    _____   ____ _____ _   _ _______ _____
#  |  ____| \ | |  __ \    |  ____| \ | |__   __|  __ \ \   / /   |  __ \ / __ \_   _| \ | |__   __/ ____|
#  | |__  |  \| | |  | |   | |__  |  \| |  | |  | |__) \ \_/ /    | |__) | |  | || | |  \| |  | | | (___
#  |  __| | . ` | |  | |   |  __| | . ` |  | |  |  _  / \   /     |  ___/| |  | || | | . ` |  | |  \___ \
#  | |____| |\  | |__| |   | |____| |\  |  | |  | | \ \  | |      | |    | |__| || |_| |\  |  | |  ____) |
#  |______|_| \_|_____/    |______|_| \_|  |_|  |_|  \_\ |_|      |_|     \____/_____|_| \_|  |_| |_____/
#


class Handler(StreamRequestHandler):
    """For use with UnixStreamServer to read in messages from the client and process them"""

    def tell_client_to_exit(self, exit_code):
        """
        This is used after the requested entry point function finishes so that the
        client is blocking while the server runs the entry point function.
        """
        self.wfile.write(json.dumps({
            "function_name": "_exit",  # Named _exit to avoid redefining builtin
            "args": [exit_code]
        }).encode('utf-8'))
        self.wfile.flush()

    def clean_exit(self, exit_value):
        """Restore stdout & stderr before shutting down otherwise it will try to send a message after closing the socket"""
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        sys.exit(exit_value)

    @staticmethod
    def socket_output_stream_wrapper_factory(output_stream):
        """Returns a class that acts as an stdout/stderr wrapper
        that sends messages as a json payload to the client"""

        class JsonPayloadOutputStreamWrapper():
            """Instantiate with name of the function in the client that will handle the text"""
            def __init__(self, client_function_name):
                self._output_stream = output_stream
                self._client_function_name = client_function_name

            def write(self, text):
                """Encode message into json and send to client.
                No trailing newline required because the client just recv's from the socket instead of using readline."""
                self._output_stream.write(json.dumps({
                    "function_name": self._client_function_name,
                    "args": [text]
                }).encode('utf-8'))

            def flush(self):  # pylint: disable=missing-function-docstring
                self._output_stream.flush()
        return JsonPayloadOutputStreamWrapper

    def handle(self):
        # Send all output to client instead of having the server print it
        OutputStreamToClientFunc = self.socket_output_stream_wrapper_factory(self.wfile)
        sys.stdout, sys.stderr = [OutputStreamToClientFunc(x) for x in ['print_server_stdout', 'print_server_stderr']]
        json_decoder = json.JSONDecoder()

        while True:
            # Note that for readline to work, the client sends a json string with a newline added to the end
            message_from_client = self.rfile.readline().decode('utf-8').strip()
            if not message_from_client:
                return
            try:
                msg_pos, msg_last = 0, len(message_from_client) - 1
                while msg_pos < msg_last:
                    request_from_client, msg_pos = json_decoder.raw_decode(message_from_client, msg_pos)

                    try:  # Update the server's env to match the client's and run the requested function:
                        os.environ = request_from_client["env"]
                        SERVER_ENTRY_POINT.run(*[request_from_client[x] for x in ["function_name", "args"]])
                        self.tell_client_to_exit(0)

                    # If an entry point function calls sys.exit it will be caught here:
                    except SystemExit as this_exit_signal:
                        print(f"Shutting down {os.path.basename(__file__)}")
                        self.tell_client_to_exit(this_exit_signal.code)
                        self.clean_exit(0)

                    # An exception here likely means that something has gone wrong in an entry point function
                    except Exception:  # pylint: disable=broad-except
                        print(traceback.format_exc(), file=sys.stderr)
                        print(f"Shutting down {os.path.basename(__file__)}")
                        self.tell_client_to_exit(1)
                        self.clean_exit(0)

            # An exception here means something went wrong with decoding the json payload from the client
            except Exception:  # pylint: disable=broad-except
                print(traceback.format_exc(), file=sys.stderr)
                print(f"Shutting down {os.path.basename(__file__)}")
                self.tell_client_to_exit(1)
                self.clean_exit(1)


def main():  # pylint: disable=missing-function-docstring
    if len(sys.argv) > 1:
        print("Error: server takes no arguments", file=sys.stderr)
        sys.exit(1)

    try:
        os.unlink(SOCKET_NAME)
    except Exception:  # pylint: disable=broad-except
        pass

    print(f"[{os.path.basename(__file__)}]: Creating socket at {SOCKET_NAME}")
    with UnixStreamServer(SOCKET_NAME, Handler) as server:
        try:
            server.serve_forever()
        finally:
            if stat.S_ISSOCK(os.stat(SOCKET_NAME).st_mode):
                os.remove(SOCKET_NAME)


if __name__ == '__main__':
    main()
