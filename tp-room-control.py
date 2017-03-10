#!/usr/bin/python

"""
Script for switching screens when presentation is
shared on Cisco TelePresence SX10/SX20/SX80 codecs.

Author: Jaroslaw Porzucek

Run under Python 2.7.x
"""

import sys
import time
from threading import Thread, Lock

import pexpect
from DaemonLite import DaemonLite

import log

wLock = Lock()

host = 'IP_ADDR'
user = 'LOGIN'
password = 'PASSWORD'

# logging
logger = log.setup_custom_logger('room_control', 'logs/room_control.log')


# run script as linux deamon
class MyDaemon(DaemonLite):

    def run(self):
        main()


class Tunnel(object):
    tunnel_command = 'ssh -o HostKeyAlgorithms=+ssh-dss -o ServerAliveInterval=15 -o ServerAliveCountMax=3 {}@{}'

    def __init__(self, host, user, password):
        logger.info('Initializing SSH connection...')
        try:
            self.host = host
            self.user = user
            self.password = password

            self.tunnel = pexpect.spawn(self.tunnel_command.format(user, host), timeout=5)
            self.tunnel.expect('Password:')
            time.sleep(1)
            self.tunnel.sendline(password)
            time.sleep(1)
            self.expect('OK')
        except Exception as e:
            sys.exit('Exception: {}'.format(e))
        else:
            logger.info("SSH tunnel successfully established!")
            return None

    def restart(self):
        for _ in xrange(5):
            try:
                logger.info('Restarting SSH tunnel...')
                self.tunnel = pexpect.spawn(
                    self.tunnel_command.format(self.user, self.host))
                self.expect('Password:')
                time.sleep(1)
                self.tunnel.sendline(self.password)
                time.sleep(1)
                self.expect('OK')
            except Exception as e:
                logger.error('Exception: {}'.format(e))
            else:
                logger.info("SSH tunnel successfully established!")

        logger.error('Cannot restart tunnel, check network connection.')
        sys.exit()
        
    def expect(self, text, timeout=5):
        if isinstance(text, basestring):
            text = [text]

        index = self.tunnel.expect([pexpect.TIMEOUT, pexpect.EOF] + text, timeout=timeout)

        if index == 0:
            logger.warning('Connection timeuout...')
        elif index == 1:
            self.restart()
        else:
            output = self.tunnel.after
            return [output, index]

    def sendline(self, command, expect):
        self.tunnel.sendline(command)
        output, _ = self.expect(expect)
        return output

    def registerEvents(self, events):
        for e in events:
            self.sendline(e, 'OK')


# check value of Video Output Connector 1 Monitor Role
def checkMonitorRole(ssh):
    output = ssh.sendline(
        'xStatus Video Output Connector 1 MonitorRole',
        r'\*s Video Output Connector 1 MonitorRole: .*'
    )

    if output.find('First') > 0:
        return True
    if output.find('Second') > 0:
        return False

# switch monitors based on Video Output Connector 1 MonitorRole status
def switchMonitors(ssh, status):
    if status == True and checkMonitorRole(ssh):
        ssh.sendline(
            "xConfiguration Video Output Connector 1 MonitorRole: Second", "OK")
        ssh.sendline(
            "xConfiguration Video Output Connector 2 MonitorRole: First", "OK")

    if status == False and not checkMonitorRole(ssh):
        ssh.sendline(
            "xConfiguration Video Output Connector 1 MonitorRole: First", "OK")
        ssh.sendline(
            "xConfiguration Video Output Connector 2 MonitorRole: Second", "OK")


def watch(ssh, value, index):
    wLock.acquire()

    # Conference Presentation Mode
    if index == 0:
        if value.find('On') > 0 or value.find('Receiving') > 0 or value.find('Sending') > 0:
            switchMonitors(ssh, True)

    # Conference Presentation LocalInstance 1 SendingMode
    if index == 1:
        if value.find('LocalRemote') > 0 or value.find('LocalOnly') > 0:
            switchMonitors(ssh, True)
        if value.find('Off') > 0:
            switchMonitors(ssh, False)

    # Video Selfview FullscreenMode
    if index == 2:
        if value.find('On') > 0:
            switchMonitors(ssh, False)

    wLock.release()

    return


def main():
    # start SSH tunnels for reading and writing
    reading_ssh = Tunnel(host, user, password)
    writing_ssh = Tunnel(host, user, password)

    events = ["xFeedback register /Status/Conference/Presentation/Mode",
              "xFeedback register /Status/Conference/Presentation/LocalInstance[@item=\'1\']/SendingMode",
              "xFeedback register Status/Video/Selfview/FullscreenMode"]

    reading_ssh.registerEvents(events)

    # listen for Status changes registered above
    while True:
        value, index = reading_ssh.expect([r'\*s Conference Presentation Mode: .*',
                                           r'\*s Conference Presentation LocalInstance 1 SendingMode: .*',
                                           r'\*s Video Selfview FullscreenMode: .*'], timeout=None)

        t = Thread(target=watch, args=(writing_ssh, value, index))
        t.setDaemon(True)
        t.start()



if __name__ == '__main__':
    daemon = MyDaemon('/tmp/telepresence-room-control.pid')
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            logger.error("Unknown command")
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s start|stop|restart" % sys.argv[0]
        sys.exit(2)
