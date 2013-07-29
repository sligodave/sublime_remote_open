
import sublime
import sublime_plugin

import os
import os.path
import time
import socket
import threading


# Track if we are currently connected or not.
# Also used to stop the server thread.
LISTEN = False


def log(msg):
    """
    Simple logging function
    """
    settings = sublime.load_settings('RemoteOpen.sublime-settings')
    if settings.get('debug', False):
        print('[Remote Open]: ' + msg)


class RemoteOpenStopServerListenCommand(sublime_plugin.WindowCommand):
    """
    Tells the server to stop listening.
    All we need to do it set the LISTEN flag to off and the server will stop.
    """
    def run(self):
        sublime.status_message('Stopping Remote Open Listening')
        global LISTEN
        LISTEN = False

    def is_enabled(self):
        return LISTEN


class RemoteOpenStartServerListenCommand(sublime_plugin.WindowCommand):
    read_rate = 1024

    def is_enabled(self):
        return not LISTEN

    def run(self, stop=False):
        if stop or LISTEN:
            sublime.status_message('Stopping Remote Open Listening')
            self.reset()
        else:
            sublime.status_message('Starting Remote Open Listening')
            self.listen()

    def reset(self):
        log('Listening Reset')
        global LISTEN
        LISTEN = False

    def listen(self):
        threading.Thread(target=self._listen).start()

    def _listen(self):
        self.reset()
        time.sleep(3)
        global LISTEN
        LISTEN = True
        log('Listening Starting %s' % os.getpid())
        serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serv.settimeout(1)
        settings = sublime.load_settings('RemoteOpen.sublime-settings')
        address = settings.get('address', 'localhost')
        port = settings.get('port', 25252)
        serv.bind((address, port))
        serv.listen(1)
        log('Listening Started %s' % os.getpid())

        c = 0
        while LISTEN:
            c += 1
            try:
                log('Listening %s %d' % (os.getpid(), c))
                connection, address = serv.accept()
                connection.settimeout(None)
                args = connection.recv(self.read_rate).decode('utf-8')
                args = args.split('\x0D')
                org_file_path = file_path = args[0]
                line_no = ''
                loc = file_path.rfind(':')
                if loc != -1 and file_path[loc + 1:].isdigit():
                    line_no = ':' + file_path[loc + 1:]
                    file_path = file_path[:loc]
                log('Remote Path Received: "%s"' % file_path)
                file_path = remote_to_local(file_path)
                log('Local Path Generated: "%s"' % file_path)
                if not os.path.exists(file_path):
                    sublime.status_message('Could not map and open "%s"' % org_file_path)
                    log('File "%s" from "%s" does not exist' % (file_path, org_file_path))
                else:
                    file_path += line_no
                    self.window.open_file(file_path, sublime.ENCODED_POSITION)
                connection.close()
                connection = None
            except socket.timeout:
                pass
        log('Listening Stopping %s' % os.getpid())
        serv.close()
        serv = None
        log('Listening Stopped %s' % os.getpid())


def remote_to_local(path):
    """
    Using the path_maps setting, we try to find the file requested by the
    remote server on this local machine. The path_maps tell us
    where the remote folders are mounted on this machine.
    """
    settings = sublime.load_settings('RemoteOpen.sublime-settings')
    for remote, local in settings.get("path_maps", {}).items():
        if path.startswith(remote):
            common = path[len(remote):]
            common = common.replace('\\', '/')
            if common.startswith('/'):
                common = common[1:]
            if local.endswith('/'):
                local = local[:-1]
            path = local + '/' + common
    path = path.replace('\\', '/')
    return path
