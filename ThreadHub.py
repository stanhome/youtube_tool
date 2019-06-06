#!/usr/bin/env python
# coding=utf-8
# @brief: MyThread inherit Thread, and can return result
# @author: stan
# @date: 20190531

import threading

class DownloadThread(threading.Thread):
    def __init__(self, func, args, **dicArgs):
        threading.Thread.__init__(self)
        self.func = func
        self.args = args
        self.startTip = dicArgs["startTip"]
        self.fileSizeByMB = dicArgs["fileSizeByMB"]
        self.doneFilePath = dicArgs["doneFilePath"]


    def getResult(self):
        return self.res

    def run(self):
        print(self.startTip)
        ## NOTE: slef.args = {"output_path": TEMP_FOLDER, "filename": None, "filename_prefix": "v_"}
        ## this parameter transfor is very IMPORTANT
        self.res = self.func(**self.args)

        # save done file for flag
        doneFile = open(self.doneFilePath, "w")
        doneFile.write("file size: %f MB" % self.fileSizeByMB)
        doneFile.close()

        print("task done: %s" % self.res)


class ListDownloadThreadFunc(object):

    def __init__(self, target, argsArray, linkStatusDic):
        """ @linkStatusDic, link url => status(True or False)
        """
        self.target = target
        self.argsArray = argsArray
        self.linkStatusDic = linkStatusDic

    def __call__(self):
        for args in self.argsArray:
            if self.linkStatusDic[args[0]] == True:
                # has already download.
                continue
            try:
                self.target(*args)
                # record link download success.
                self.linkStatusDic[args[0]] = True

            except Exception as e:
                raise e
