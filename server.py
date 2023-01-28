#!/usr/bin/env python3

from socketserver import UnixStreamServer, StreamRequestHandler
import traceback
import json
import sys
import os


SOCKET_NAME = "/tmp/test"


class ServerEntryPoints():
    """Instantiate this class, then use that instance as a decorator for any functions that are to be used as an entry point.
    The idea is that the "server" will run any functions that are called by the client, but since the server doesn't die
    between those calls, the state of the python script (running as the server) is maintained.
    So for example, if one entry point instantiated a global variable, other entry points could use that variable.
    """
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

        error_message = f"""\"{func_name}\" is not a valid entry point function.

Remember to first decorate those functions with @SERVER_ENTRY_POINT like this:

@SERVER_ENTRY_POINT
def my_entry_point():
    do something here..."""
        raise NameError(error_message)


SERVER_ENTRY_POINT = ServerEntryPoints()


@SERVER_ENTRY_POINT
def set_thing(value):
    """example entry point where we create a global"""
    globals()['THING'] = value
    print(f"global variable \"THING\" is now {THING}")


@SERVER_ENTRY_POINT
def get_thing():
    """another example entry point where we read the new global from the first example"""
    print(f"thing = {THING}")


class Handler(StreamRequestHandler):
    """For use with ThreadedUnixStreamServer to read in messages from the client and process them"""

    def tell_client_to_exit(self, exit_code=0):
        """
        This is used after the requested entry point function finishes so that the
        client is blocking while the server runs the entry point function.
        """
        self.wfile.write(json.dumps({
            "function": "_exit",  # Named _exit to avoid redefining builtin
            "args": [exit_code]
        }).encode('utf-8'))
        self.wfile.flush()

    def clean_exit(self, exit_value=0):
        """Restore stdout & stderr before shutting down otherwise it will try to send a message after closing the socket"""
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        sys.exit(exit_value)

    @staticmethod
    def socket_output_stream_wrapper_factory(output_stream):
        """Returns a class that acts as an stdout/stderr wrapper
        that sends messages as a json payload over the output stream"""

        class JsonPayloadOutputStreamWrapper():
            """Instantiate with name of the function in the client that will handle the text"""
            def __init__(self, client_function_name):
                self._output_stream = output_stream
                self._client_function_name = client_function_name

            def write(self, text):  # pylint: disable=missing-function-docstring
                if text.strip() == '':
                    return
                # Unlike the client, here we don't need the trailing newline
                # because the client just recv's from the socket instead of using readline
                self._output_stream.write(json.dumps({
                    "function": self._client_function_name,
                    "args": [text]
                }).encode('utf-8'))

            def flush(self):  # pylint: disable=missing-function-docstring
                self._output_stream.flush()
        return JsonPayloadOutputStreamWrapper

    def handle(self):
        # Send all output to client instead of having the server print it
        OutputStreamToClientFunc = self.socket_output_stream_wrapper_factory(self.wfile)
        sys.stdout, sys.stderr = [OutputStreamToClientFunc(x) for x in ['print_server_stdout', 'print_server_stderr']]

        while True:  # pylint: disable=too-many-nested-blocks

            # Note that for readline to work, the client sends a json string with a newline added to the end
            message_from_client = self.rfile.readline().decode('utf-8').strip()
            if not message_from_client:
                return
            try:
                msg_index, msg_length = 0, len(message_from_client) - 1
                while msg_index < msg_length:
                    msg_object, msg_index = json.JSONDecoder().raw_decode(message_from_client, msg_index)

                    # Handle special case of shutting the server down:
                    if msg_object.get('function') == 'exit':
                        print(f"Shutting down {os.path.basename(__file__)}")
                        self.tell_client_to_exit(0)
                        self.clean_exit()

                    else:
                        try:
                            SERVER_ENTRY_POINT.run(*[msg_object[x] for x in ["function", "args"]])
                            return_value = 0
                        except Exception:  # pylint: disable=broad-except
                            print(traceback.format_exc(), file=sys.stderr)
                            return_value = 1

                        if return_value == 0:
                            self.tell_client_to_exit(return_value)
                        else:
                            print(f"Shutting down {os.path.basename(__file__)}")
                            self.tell_client_to_exit(return_value)
                            self.clean_exit()

            except Exception:  # pylint: disable=broad-except
                print(traceback.format_exc(), file=sys.stderr)
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

    with UnixStreamServer(SOCKET_NAME, Handler) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
