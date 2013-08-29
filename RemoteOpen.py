
import sublime
import sublime_plugin

import os
import os.path
import sys
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

                # Bring sublime to front
                if(sublime.platform() == 'osx'):
                    # Concept from rsub, check it out! https://github.com/henrikpersson/rsub/
                    # Calls out to system python2 as ScriptBridge isn't installed in sublimes python3

                    import subprocess
                    # The major python version matches the ST version
                    version = sys.version_info[0]

                    command = "python -c "
                    command += "\"from ScriptingBridge import SBApplication;"
                    command += "SBApplication.applicationWithBundleIdentifier_"
                    command += "('com.sublimetext.%d').activate()\"" % version
                    subprocess.call(command, shell=True)
                # Linux Not implemented yet. I need a box to figure it and test out on
                # elif(sublime.platform() == 'linux'):
                #     import subprocess
                #     subprocess.call("wmctrl -xa 'sublime_text.sublime-text-3'", shell=True)

                args = args.split('\x0D')
                org_paths = paths = args
                line_nos = []

                for i in range(len(paths)):
                    path = paths[i]
                    line_nos.append('')
                    loc = path.rfind(':')
                    if loc != -1 and path[loc + 1:].isdigit():
                        line_nos[-1] = ':' + path[loc + 1:]
                        paths[i] = path[:loc]
                log('Remote Paths Received: %s' % paths)
                for i in range(len(paths)):
                    paths[i] = remote_to_local(paths[i])
                log('Local Path Generated: %s' % paths)

                for i, path in enumerate(paths):
                    if not os.path.exists(path):
                        sublime.status_message('Could not map and open "%s"' % org_paths[i])
                        log('Path "%s" from "%s" does not exist' % (path, org_paths[i]))
                        continue
                    if os.path.isdir(path):
                        if settings.get('open_directory_contents', True):
                            file_paths = get_file_paths(
                                path,
                                settings.get('open_directory_recursively', False)
                            )
                        else:
                            sublime.status_message('RemoteOpen: Not configured to open directories, so "%s" ignored.' % path)
                            log('Not configured to open directories, so "%s" ignored.' % path)
                    else:
                        file_paths = ['%s%s' % (path, line_nos[i])]
                    for file_path in file_paths:
                        sublime.status_message('RemoteOpen: Opening file "%s"' % file_path)
                        log('Opening file "%s" from "%s"' % (file_path, org_paths[i]))
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


def get_file_paths(path, recursive=False):
    file_paths = []
    for root, dirs, files in os.walk(path):
        file_paths.extend([os.path.join(root, x) for x in files])
        if not recursive:
            break
    return file_paths
