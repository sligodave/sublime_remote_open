
import socket
import os.path


def send_request(address='localhost', port=25252, args=None):
    """
    Connect to the server at the supplied address and port.
    Send the file path provided.
    It is recommended that it is an absolute path,
    those are easier to translate on the server side to a mapped
    directory
    """
    if not args:
        print('You must supply at least a file to be '
              'opened by the listening Sublime Text')
        return
    args[0] = os.path.abspath(args[0])
    args = '\x0D'.join(args)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((address, port))
    except socket.error:
        print('Could not connect to remote Sublime Text '
              'Instance at "%s:%d". Is it listening?' % (address, port))
    else:
        s.sendall(args.encode('utf8'))
        s.close()

if __name__ == '__main__':
    """
    If invoked from the command line, the arguments are as follows:
    - Address to connect to, defaults to localhost.
    - Port to connect to, defaults to 25252.
    - Path to the file to open
    - Anything else you want to pass
    - ...
    - ...
    """
    import sys
    send_request(sys.argv[1], int(sys.argv[2]), sys.argv[3:])
