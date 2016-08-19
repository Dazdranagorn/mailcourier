#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MailCourier main logic module
"""

import imaplib
import smtplib
import time
import os
import re
import ssl
import socket
import email
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from multiprocessing import Process, Queue, Value
import signal
import psutil
import admission


def transfer(server, message, use_extra=False):
    """ Func that send email via SMTP

    :param server: copy of Mailserver object
    :param message: standart email message
    :param use_extra: flag to use extra parametrs of the server (usually when some error occurs previously)
    :return: error string (empty = no error occurs)
    """
    if use_extra:
        typ_s = server.extra_server_type
        out_s = server.extra_server
        out_p = server.extra_port
        login = server.extra_login
        password = server.extra_password
    else:
        typ_s = server.outgoing_server_type
        out_s = server.outgoing_server
        out_p = server.outgoing_port
        login = server.login
        password = server.password
    try:  # connect to the server
        if typ_s == 'smtp_ssl':
            post = smtplib.SMTP_SSL(out_s, out_p, timeout=15)
        elif typ_s == 'smtp':
            post = smtplib.SMTP(out_s, out_p, timeout=15)
            try:  # try to catch some exceptions but it is not tragedy
                post.starttls()
            except smtplib.SMTPHeloError:
                print "({})Connection smtp-starttls failed. SMTPHeloError".format(os.getpid())
            except smtplib.SMTPException:
                print "({})Connection smtp-starttls failed. CommonError".format(os.getpid())
        else:
            post = None
        if post:
            try:  # login to the server
                post.login(login, password)
                try:  # then send the email
                    post.sendmail(login, server.destination, message)
                    status = ""
                except smtplib.SMTPRecipientsRefused:
                    status = "Send smtp failed. SMTPRecipientsRefused."
                except smtplib.SMTPHeloError:
                    status = "Send smtp failed. SMTPHeloError."
                except smtplib.SMTPSenderRefused:
                    status = "Send smtp failed. SMTPSenderRefused."
                except smtplib.SMTPDataError:
                    status = "Send smtp failed. SMTPDataError."
                except smtplib.SMTPException:
                    status = "Send smtp failed. SMTPException."
            except smtplib.SMTPHeloError:
                status = "Login smtp failed. HeloError."
            except smtplib.SMTPAuthenticationError:
                status = "Login smtp failed. AuthenticationError."
            except smtplib.SMTPException:
                status = "Login smtp failed CommonError."
            post.quit()  # logout from the server
        else:
            status = "Type smtp is unknown."
    except ssl.SSLError:
        status = "Connection smtp SSLError."
    except socket.timeout:
        status = "Connection smtp socket.timeout."
    except smtplib.SMTPException:
        status = "Connection smtp failed."
    return status


def get_folder_name(folder):
    """ Decomposing folder record

    :param folder: record about the folder
    :return: get only folder's name
    """
    list_response_pattern = re.compile(r'\((?P<flags>.*?)\) "(?P<delimiter>.*)" (?P<name>.*)')
    flags, delimiter, name = list_response_pattern.match(folder).groups()
    return name


def make_box_search(server, box, fldr_name, flag):
    """ Make the search for seen/unseen emails

    :param server: copy of Mailserver object
    :param box: copy of IMAP-descriptor to access the server
    :param fldr_name: the name of the folder in the box to search
    :param flag: points to seen or unseen emails
    :returns:
    execs -- count of executed messages
    status -- error string (empty = no error occurs)
    """
    execs = 0  # count of executed messages
    try:
        box.select(fldr_name)  # open the folder
        try:  # search for emails
            typ, data = box.search(None, flag)
            status = ""
            if len(data[0].split()) > 0:
                print "({})Box {}/{} has {} {},".format(os.getpid(), server.login, fldr_name, len(data[0].split()),
                                                        flag)
                for num in data[0].split():  # for each email we found...
                    typ, data = box.fetch(num, '(RFC822)')
                    if flag == '(SEEN)':  # check for old emails, live time get from server.msg_livetime
                        envelope = email.message_from_string(data[0][1])
                        date_tuple = email.utils.parsedate_tz(envelope['Date'])
                        delete_message = True
                        if date_tuple:
                            if int(email.utils.mktime_tz(date_tuple)) > \
                                            int(time.time())-server.msg_livetime:
                                delete_message = False
                        if delete_message:
                            execs += 1
                            box.store(num, '+FLAGS', '\\DELETED')
                        box.expunge()  # remove marked messages
                    else:  # check for new emails
                        tmp = transfer(server, data[0][1])  # try to forward it
                        if tmp == "":
                            box.store(num, '+FLAGS', '\\SEEN')
                            execs += 1
                        else:  # if forwarding fails send the message from extra SMTP-server
                            print "({})\"{}\" on {}/{}#{}".format(os.getpid(), tmp, server.login, fldr_name, num)
                            tmp = transfer(server, data[0][1], True)
                            if tmp == "":
                                box.store(num, '+FLAGS', '\\SEEN')
                                print "({})Send {}/{}#{} via {}".format(os.getpid(), server.login, fldr_name, num,
                                                                        server.extra_login)
                                execs += 1
                            else:  # if sending fails to mark this email as UNSEEN to retry next time
                                tmp = transfer(server, data[0][1], True)
                                box.store(num, '-FLAGS', '\\SEEN')
                                status = "{}\nSend {}/{}#{} failed".format(tmp, server.login, fldr_name, num)
        except socket.error:
            status = "Search imap for {} in {}/{} failed due to disconnect".format(flag, server.login, fldr_name)
        except imaplib.IMAP4.error:
            status = "Search imap for {} in {}/{} failed, ".format(flag, server.login, fldr_name)
        box.close()  # close opened folder
    except imaplib.IMAP4.error:
        status = "Select imap in {}/{} failed, ".format(server.login, fldr_name)
    return execs, status


def read(server):
    """ This function get IMAP access to the server to get the emails

    :param server: copy of Mailserver object
    :returns:
    executed_msg_cnt -- count of executed messages
    status -- error string (empty = no error occurs)
    """
    executed_msg_cnt = 0  # the sum of all executed emails in the mailbox
    try:
        box = imaplib.IMAP4_SSL(server.incoming_server, server.incoming_port)
        try:
            box.login(server.login, server.password)
            typ, fldrs = box.list()
            if typ == 'OK':
                status = ""
                for fldr in fldrs:  # for each folder in the box search seen and unseen emails
                    name = get_folder_name(fldr)
                    num, tstring = make_box_search(server, box, name, '(SEEN)')
                    executed_msg_cnt += num
                    status += tstring
                    num, tstring = make_box_search(server, box, name, '(UNSEEN)')
                    executed_msg_cnt += num
                    status += tstring
            else:
                status = "Box {} has no folders ".format(server.login)
            box.logout()
        except imaplib.IMAP4.error:
            status = "Login imap {} failed ".format(server.login)
    except imaplib.IMAP4.error:
        status = "Connection imap {}{} failed ".format(server.incoming_server, server.incoming_port)
    #  there are global except because unstable behavior of connect() in imaplib module
    #  and countless types of it's fail reasons
    except:
        status = "Connection imap {}{} failed due to shit".format(server.incoming_server, server.incoming_port)
    return executed_msg_cnt, status,


def compose_errrept(emiter, destination, theme, text):
    """ Create the email with standard fields

    :param emiter: email address for FROM (string)
    :param destination: email address for TO (string)
    :param theme: subject of email
    :param text: message body of email
    :return: standard email message
    """
    msg = MIMEMultipart()
    msg['From'] = emiter
    msg['To'] = destination
    msg['Subject'] = theme
    msg.attach(MIMEText(text, 'plain'))
    return msg.as_string()


def has_error(server, text):
    """ Function checks error timer of the server and send the last error description

    :param server: copy of Mailserver object
    :param text: error string to send
    :return: new state of the server (it has new values of refresh_timer and refresh_factor)
    """
    if server.extend_refresh_timer() > 8 * 60 * 60:  # Error patience 8 hours
        transfer(server, compose_errrept(server.login, server.destination, "MailCourier error message", text), True)
        server.clear_refresh_factor()
    print "({})Error on {}: {}".format(os.getpid(), server.login, text)
    # to work around mutable objects return its new state
    return server


def check_mail(queue, tout, cid):
    """ Controls mailbox

    :param queue: wrap to in and out copy of Mailserver object
    :param tout: time that past from the last search
    :param cid: value-wrap to output the id of this proc
    :return: queue
    """
    server = queue.get()
    cid.value = os.getpid()
    if server.is_stinky(tout):
        print "\n({})--------- {} ---------------".format(cid.value, server.login)
        ex, ret = read(server)
        print "({})(proceed {})".format(cid.value, ex)
        if ret == "":
            server.clear_refresh_factor()
        else:
            server = has_error(server, ret)
    return queue.put(server)


def main(ppid):
    """ Main function of MailCourier
    create list of Mailservers
    starts new procs (workers) to check every Mailserver
    controls timeout of child procs then kill it

    Note:
    to keep app alive 18h a day i use my external service
    so mailcourier works from 09:00 to 02:00 (17 hours) and 30 minutes in the early morning
    cron params is
        */20 0-1,9-23 * * *   /usr/local/php54/bin/php getreq2mailcourier.php
        0   6         * * *   /usr/local/php54/bin/php getreq2mailcourier.php
    alternative is 'http://kaffeine.herokuapp.com/' ( my app go to sleep any way :( )

    :param ppid: pid of the parent proc
    :return: nothing
    """
    refresh_rate = 60*5  # full update period 5min
    s = admission.Admission()  # create list of Mailservers
    status = "MailCourier status: {}".format("Restarting")
    print "({}){}, flask pid {}".format(os.getpid(), status, ppid)
    startime = time.gmtime()
    # notify me if MailCourier was restarted after 9:10(GMT+3)
    if startime.tm_hour*60 + startime.tm_min > 370:  # (9-3)*60 + 10 = 360 + 10
        msg = time.strftime("Server time: %Y-%m-%d %H:%M:%S \n", startime)
        msg += "\n\nMailbox list:"
        for i in range(0, len(s.servers), 1):
            msg += "\n{}) {} -> {}".format(i+1, s.servers[i].login, s.servers[i].destination)
        msg += "\n"
        transfer(s.servers[0], compose_errrept(s.servers[0].extra_login, s.servers[0].destination, status, msg), True)
    while psutil.pid_exists(ppid) or ppid == 0:  # check for the death of the parent proc
        for i in range(0, len(s.servers), 1):
            queue = Queue()
            cid = Value('i', 0)
            queue.put(s.servers[i])
            p = Process(target=check_mail, args=(queue, refresh_rate, cid,), )
            time_temp = time.time()
            p.start()
            p.join(refresh_rate / len(s.servers))
            # return mutated object from multiproc queue
            serv = queue.get()
            if p.is_alive():
                p.terminate()
                if cid > 0:
                    os.kill(cid.value, signal.SIGKILL)
                serv = has_error(s.servers[i], "Job timeout on {}".format(s.servers[i].login))
                time.sleep(1)
            else:
                time_temp = refresh_rate / len(s.servers) - (time.time() - time_temp)
                if time_temp >= 1:
                    time.sleep(time_temp)  # sleep if finish this mailserver early
            s.servers[i] = serv
    # never get there
    print "({})MailCourier status: {}".format(os.getpid(), "Down")


if __name__ == "__main__":
    main(0)
