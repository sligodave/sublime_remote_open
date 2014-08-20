
import sublime
import sublime_plugin

import os
import os.path
import sys
import socket
import threading
import subprocess

try:
    import socketserver
except ImportError:
    import SocketServer as socketserver
    ConnectionRefusedError = socket.error


# Used to stop print statements from overlapping eachother.
LOCK = threading.Lock()


def get_settings(setting=None, default=None):
    """
    FIXME: Maybe cache the settings,
    rather than getting them every time.
    """
    settings = sublime.load_settings('RemoteOpen.sublime-settings')
    if setting is not None:
        return settings.get(setting, default)
    return settings


def client(message=None):
    """
    Test to see if the client is alive.
    You can also optionally send a message
    but it doesn't wait for a response.
    """
    host = get_settings('host', get_settings('address', 'localhost'))
    port = get_settings('port', 25252)
    alive = True

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(.1)

    try:
        sock.connect((host, port))
    except (ConnectionRefusedError, socket.timeout):
        alive = False

    if alive is True:
        if message is not None:
            try:
                sock.sendall(message.encode('utf8'))
            except (ConnectionRefusedError, socket.timeout):
                alive = False
        sock.close()
    return alive


def log(msg):
    """
    Simple logging function.
    Tries to be thread safe when printing.
    Returns the message for convenience.
    """
    if get_settings('debug', False):
        with LOCK:
            print('[Remote Open]: ' + msg)
    return msg


def remote_to_local(path):
    """
    Using the path_maps setting, we try to find the file requested by the
    remote server on this local machine. The path_maps tell us
    where the remote folders are mounted on this machine.
    """
    path = path.replace('\\', '/')
    for remote, local in get_settings("path_maps", {}).items():
        remote = remote.replace('\\', '/')
        local = local.replace('\\', '/')
        if path.startswith(remote):
            common = path[len(remote):]
            if common.startswith('/'):
                common = common[1:]
            if local.endswith('/'):
                local = local[:-1]
            path = local + '/' + common
            break
    return path


def get_file_paths(path, recursive=False):
    """
    Generate a list of all files under a path.
    We use this when opening entire directories.
    """
    file_paths = []
    for root, dirs, files in os.walk(path):
        file_paths.extend([os.path.join(root, x) for x in files])
        if not recursive:
            break
    return file_paths


class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        """
        Handle a request from a remote machine.
        Or it's a ping/die request from sublime text.
        """
        data = self.request.recv(1024).decode('utf8')
        # Ignore empty client messages. This helps us ignore empty pings
        if not data.strip():
            return

        log('Received Request "%s"' % (data))

        if data == get_settings('die_flag', '__REMOTE__OPEN__DIE__'):
            log('Shutdown request received. Server shutting down.')
            self.server.shutdown()
            return

        if(sublime.platform() == 'osx'):
            # Concept from rsub, check it out! https://github.com/henrikpersson/rsub/
            # Calls out to system python2 as ScriptBridge isn't installed in sublimes python3
            # Conveniently the python major python version matches the ST version
            version = sys.version_info[0]
            command = "python -c "
            command += "\"from ScriptingBridge import SBApplication;"
            command += "SBApplication.applicationWithBundleIdentifier_"
            command += "('com.sublimetext.%d').activate()\"" % version
            subprocess.call(command, shell=True)
            # TODO: Add Linux and Windows support for subl bringing to the front.

        data = data.split('\x0D')
        org_paths = paths = data
        line_nos = []

        for i in range(len(paths)):
            path = paths[i]
            line_nos.append('')
            loc = path.rfind(':')
            if loc != -1 and path[loc + 1:].isdigit():
                line_nos[-1] = ':' + path[loc + 1:]
                paths[i] = path[:loc]

        log('Remote Paths Received: "%s"' % paths)
        for i in range(len(paths)):
            paths[i] = remote_to_local(paths[i])
        log('Local Paths Generated: "%s"' % paths)

        for i, path in enumerate(paths):
            if not os.path.exists(path) and not get_settings('create_if_missing', True):
                sublime.status_message(log('Path "%s" from "%s" does not exist' % (path, org_paths[i])))
                continue
            if os.path.isdir(path):
                if get_settings('open_directory_contents', True):
                    file_paths = get_file_paths(
                        path,
                        get_settings('open_directory_recursively', False)
                    )
                else:
                    sublime.status_message(log('Not configured to open directories, so "%s" ignored.' % path))
            else:
                file_paths = ['%s%s' % (path, line_nos[i])]
            for file_path in file_paths:
                sublime.status_message(log('Opening file "%s" from "%s"' % (file_path, org_paths[i])))
                sublime.active_window().open_file(file_path, sublime.ENCODED_POSITION)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


class RemoteOpenStartServerCommand(sublime_plugin.WindowCommand):
    def run(self, stop=False):
        """
        Start the server to listen for remote requests.
        """
        self.window.run_command('remote_open_stop_server')
        sublime.status_message(log('Starting Remote Open Server'))
        host = get_settings('host', get_settings('address', 'localhost'))
        port = get_settings('port', 25252)

        server = ThreadedTCPServer((host, port), ThreadedTCPRequestHandler)
        server.server_address
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

    def is_enabled(self):
        return client() is False


class RemoteOpenStopServerCommand(sublime_plugin.WindowCommand):
    """
    Tells the server to stop listening.
    """
    def run(self):
        sublime.status_message(log('Stopping Remote Open Server'))
        client(get_settings('die_flag', '__REMOTE__OPEN__DIE__'))

    def is_enabled(self):
        return client() is True


def listen_on_startup():
    if get_settings('listen_on_startup'):
        sublime.active_window().run_command('remote_open_start_server')


sublime.set_timeout(listen_on_startup, 5000)
