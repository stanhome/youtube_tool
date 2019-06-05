#!/usr/bin/env python
# coding=utf-8
# @brief: MyThread inherit Thread, and can return result
# @author: stan
# @date: 20190531

import threading

class MyThread(threading.Thread):
    def __init__(self, func, args, startTip):
        threading.Thread.__init__(self)
        self.func = func
        self.args = args
        self.startTip = startTip


    def getResult(self):
        return self.res

    def run(self):
        print(self.startTip)
        self.res = self.func(**self.args)
        print("task done: %s" % self.res)
