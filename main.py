#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Wrapper for MailCourier adds Flask-WSGI support for web access
"""

import os
import time
import flask
import mailcourier
from multiprocessing import Process

app = flask.Flask(__name__)
has_child = False  # global var to prevent of starting new instances of MailCourier
startime = 0  # global var to hold start time

@app.route("/")
def index():
    """ Func performs on web access to https://mailcourier.herokuapp.com/

    :return: HTML document, here simple status string

    """
    pid = os.getpid()

    global has_child
    global startime
    if not has_child:  # get there on the first start after idle
        has_child = True
        p = Process(target=mailcourier.main, args=(pid,),)
        p.start()
        startime = time.localtime()
        status = "Welcome!\nMailCourier is started. {}".format(time.strftime("%Y-%m-%d %H:%M:%S", startime))
    else:
        status = "MailCourier is working for {}, maybe... Check it on heroku log. Thank you.".format(time.strftime("%H:%M:%S", time.gmtime(time.time()-time.mktime(startime))))
    print status
    return status


if __name__ == "__main__":
    app.run()
