#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This module describes administrative functions such as Mailserver options and it access methods
"""


class Mailserver:
    """
    This class holds mail server access points, login and password, etc.
    """
    refresh_timeout = 60*5  # basic time to be rechecked for new emails = 5min

    def set_refresh_timer(self, time=refresh_timeout):
        """ Set new value to refresh_timer

        :param time:
        :return: noting
        """
        self.refresh_timer = time

    def is_stinky(self, step):
        """ Read the status of Mailserver

        :param step: time has past from the last access to Mailserver
        :return: Mailserver is ready to be rechecked or not (boolean)
        """
        self.refresh_timer = self.refresh_timer - step
        if self.refresh_timer <= 0:
            self.set_refresh_timer()
            ret = True
        else:
            ret = False
        return ret

    def clear_refresh_factor(self):
        self.refresh_factor = 1

    def extend_refresh_timer(self):
        """ Increase refresh_factor and extend refresh_timer.

        Note:
        Run it when error occurs.

        :return: new value of refresh_timer
        """
        # factor order is(chill out to the next access):
        # 1(5min) 2(10min) 3(15min) 6(1hour) 12(1hour) 24(2hour) 48(4hour) 96(8hour) then i make reset in 'has_error()'
        # the last 2 hours of the day will be: 1(5min) 2(10min) 3(15min) 6(1hour) 12(1hour)
        if self.refresh_factor % 3 == 0:
            self.refresh_factor *= 2
        else:
            self.refresh_factor += 1
        self.set_refresh_timer(self.refresh_factor * self.refresh_timeout)
        return self.refresh_timer

    def __init__(self, incoming_server_type, incoming_server, incoming_port,
                 outgoing_server_type, outgoing_server, outgoing_port,
                 login, password, destination, msg_livetime,
                 extra_server_type, extra_server, extra_port, extra_login, extra_password):
        """ Creates new Mailserver and set up fields of the record
        For usage example look at Admission.get_next_serveropt()

        :param incoming_server_type: IMAP or IMAP+SSL (string)
        :param incoming_server: IMAP server address (string)
        :param incoming_port: IMAP server port (int)
        :param outgoing_server_type: SMTP or SMTP+SSL (string)
        :param outgoing_server: SMTP server address(string)
        :param outgoing_port: SMTP server port(int)
        :param login: email address (string)
        :param password: (string)
        :param destination: email address to forwarding (string)
        :param msg_livetime: the age of seen messages to be deleted (int)
        :param extra_server_type: emergency SMTP or SMTP+SSL (string)
        :param extra_server: emergency server address( string)
        :param extra_port: emergency SMTP server port (int)
        :param extra_login: emergency email address (string)
        :param extra_password: (string)
        """
        self.incoming_server_type = incoming_server_type
        self.incoming_server = incoming_server
        self.incoming_port = incoming_port
        self.outgoing_server_type = outgoing_server_type
        self.outgoing_server = outgoing_server
        self.outgoing_port = outgoing_port
        self.login = login
        self.password = password
        self.destination = destination
        self.msg_livetime = msg_livetime

        self.extra_server_type = extra_server_type
        self.extra_server = extra_server
        self.extra_port = extra_port
        self.extra_login = extra_login
        self.extra_password = extra_password

        # clear refresh_factor and refresh_timeout
        self.refresh_factor = 1
        self.refresh_timer = self.refresh_timeout


class Admission:
    """
    This class is a list of Mailservers
    """
    records = 0
    servers = []

    @staticmethod
    def get_next_serveropt(self):
        """ This function reads params for the next Mailserver from my external service

        :returns:
        ret -- answer 'OK' or 'NO' (string)
        val -- copy of Mailserver object
        """
        val = None
        ret = 'NO'

        # Test output:
        # if self.records < 1
        #     ret = 'OK'
        #     val = Mailserver('imap_ssl', 'imap.example.com', 993,
        #                      'smtp_ssl', 'smtp.example.com', 465,
        #                      'username@example.com', 'qwerty', 'newusername@mymail.com', 1*(60*60*24*31),
        #                      'smtp', 'smtp.posta.com', 587, 'otherusername@posta.com', 'qwe123')

        return ret, val

    def __init__(self):
        """
        Fill the list of Mailservers
        """
        typ = 'OK'
        while typ == 'OK':
            typ, server = self.get_next_serveropt(self)
            if typ == 'OK':
                self.servers.append(server)
                self.records += 1
