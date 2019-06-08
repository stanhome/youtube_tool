#!/usr/bin/env python
# coding=utf-8
# @brief: Youtube download
# @author: stan
# @date: 20190531

import os, traceback, sys, subprocess
import time
import subprocess
import threading
import re
from multiprocessing import cpu_count
from string import Template
from pytube import YouTube, Playlist, request
from ThreadHub import DownloadThread, ListDownloadThreadFunc

# 同时下载数量
DOWNLOAD_TASK_CUNT = 3

ITAG_1080P_WEBM = 248
ITAG_1080P_MP4 = 137
ITAG_720P_MP4_WITH_AUDIO = 22

CWD = os.getcwd()
TEMP_FOLDER = os.path.join(CWD, "temp")
OUTPUT_FOLDER = os.path.join(CWD, "output")
FFMPEG_FILE_PATH = os.path.join(CWD, "ffmpeg")
CMD_FFMPEG_TPL = Template(FFMPEG_FILE_PATH + ' -y -i "${video}" -i "${audio}" "${out_file_name}.mp4"  -c:v libx264 -c:a aac')

# keep one ffmpeg progress at one time
s_keepSingleFFmpegLock = threading.Lock()

def mkdir(path):
    # uPath = path.decode("utf-8")
    isFolderExist = os.path.exists(path)
    if not isFolderExist:
        os.makedirs(path)
    
def downloadSingle(url, filename_prefix=None, subFolder=None):
    print("download: %s" % str(url))
    yt = YouTube(url)
    
    fileName = yt.title
    if filename_prefix:
        fileName = str(filename_prefix) + "_" + fileName

    outputFolder = OUTPUT_FOLDER
    if subFolder:
        outputFolder = os.path.join(outputFolder, subFolder)
        mkdir(outputFolder)

    outputFileName = os.path.join(outputFolder, fileName)
    print("download to %s" % outputFileName)


    outputFullPath = outputFileName + ".mp4"
    if os.path.exists(outputFullPath):
        print("[*] skip, file exists: %s" % outputFullPath)
        return


    # 1. start download video
    videoToDownloadStream = yt.streams.get_by_itag(ITAG_1080P_WEBM)

    while videoToDownloadStream is None:

        videoToDownloadStream = yt.streams.get_by_itag(ITAG_1080P_MP4)
        if videoToDownloadStream:
            break

        print("[w] 1080p video srouce not found.")
        videoToDownloadStream = yt.streams.get_by_itag(ITAG_720P_MP4_WITH_AUDIO)

        if videoToDownloadStream:
            break

        videoToDownloadStream = yt.streams.filter(adaptive=True).first()

    if videoToDownloadStream is None:
        print("[E] video stream not found.")


    fileSizeByMB = videoToDownloadStream.filesize / 1048576.0
    videoTip = "download video stream(%s), size(%f MB) to save:%s" % (str(videoToDownloadStream), fileSizeByMB, videoToDownloadStream.default_filename)


    if videoToDownloadStream.is_progressive:
        # video with audio, we can download indirectly.
        print("videoToDownloadStream.is_progressive == TRUE, video with audio. ")
        prefix = filename_prefix + "_" if filename_prefix else None

        #judgement is file exist
        fileToDownloadName = filename_prefix + videoToDownloadStream.default_filename if prefix else videoToDownloadStream.default_filename
        outputFullPath = os.path.join(outputFolder, fileToDownloadName)
        if os.path.exists(outputFullPath):
            print("[*] skip, file exists: %s" % outputFullPath)
        else: 
            videoSavePath = videoToDownloadStream.download(output_path=outputFolder, filename_prefix=prefix)
            print("downlaod done: %s", videoSavePath)

        return

    # judgement whether the video file exists
    videoFilePath = os.path.join(TEMP_FOLDER, "v_" + videoToDownloadStream.default_filename)
    videoDoneFilePath = videoFilePath + ".done"
    videoDownloadTask = None
    if not os.path.exists(videoDoneFilePath):
        # single thread
        # print("download video stream(%s), size(%f MB) to save:%s" % (str(videoToDownloadStream), videoToDownloadStream.filesize / 1048576.0, videoToDownloadStream.default_filename))
        # videoFilePath = videoToDownloadStream.download(output_path=TEMP_FOLDER, filename=None, filename_prefix="v_")
        # print("download done: %s" % videoFilePath)

        # multiple thread
        videoDownloadTask = DownloadThread(videoToDownloadStream.download, 
            {"output_path": TEMP_FOLDER, "filename": None, "filename_prefix": "v_"},
            startTip=videoTip, filesize=videoToDownloadStream.filesize, doneFilePath=videoDoneFilePath)

        videoDownloadTask.start()
    else:
        print("skip temp file because of file has existed: %s" % videoDoneFilePath)


    # 2. start download audio
    audioToDownloadStream = yt.streams.filter(only_audio=True).order_by("abr").desc().first()
    #judgement whether the audio file exists
    audioFilePath = os.path.join(TEMP_FOLDER, "a_" + audioToDownloadStream.default_filename)
    audioDoneFilePath = audioFilePath + ".done"
    if not os.path.exists(audioDoneFilePath):

        # single thread
        fileSizeByMB = audioToDownloadStream.filesize / 1048576.0
        print("download audio stream(%s), size(%f MB) to save: %s" % (str(audioToDownloadStream), fileSizeByMB, audioToDownloadStream.default_filename))
        audioFilePath = audioToDownloadStream.download(output_path=TEMP_FOLDER, filename_prefix='a_')

        fileRealSize = os.path.getsize(audioFilePath)
        if fileRealSize == audioToDownloadStream.filesize:
            # save done file for flag
            doneFile = open(audioDoneFilePath, "w")
            doneFile.write("file size: %f MB" % fileSizeByMB)
            doneFile.close()
            print("download done: %s" % audioFilePath)
        else:
            raise Exception("audio file download failed. file size is wrong. stream file size(%d), real file size(%d)" % (audioToDownloadStream.filesize, fileRealSize))
            return
    else:
        print("skip temp file because of file has existed: %s" % audioDoneFilePath)


    # 3. download caption file.
    caption = yt.captions.get_by_language_code('en')
    if caption is None:
        print("english caption not found.")
    else:
        print("save caption to srt file:" + str(caption))
        file = open(outputFileName + ".srt", "w")
        file.write(caption.generate_srt_captions().replace("[Music]", ""))
        file.close()


    # 4. wait all task finish.
    if videoDownloadTask:
        videoDownloadTask.join()
        videoFilePath = videoDownloadTask.getResult()


    # 5. merge video and audio
    # ffmpeg -y -i %video% -i %audio% "output_file.mp4"  -c:v libx264 -c:a aac
    mergedCmd = CMD_FFMPEG_TPL.substitute(video=videoFilePath, audio=audioFilePath, out_file_name=outputFileName)
    # keep one ffmpeg at one time
    s_keepSingleFFmpegLock.acquire()
    print(mergedCmd)
    # p = subprocess.Popen(mergedCmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    p = subprocess.Popen(mergedCmd)
    while p.poll() is None:
        time.sleep(1)
        # line = p.stdout.readline()
        # line = line.strip()
        # if line:
        #     print("[ffmpeg]:" + line)

    if p.returncode == 0:
        print("%s.mp4 merged success" % (fileName))
    else:
        print("[e]may be merged failed.")
    s_keepSingleFFmpegLock.release()


# record link download status: link url => status(True or False)
s_linkStatusDic = {}


def downloadList(url, maxCount = None, start=None, end=None):
    print("download Youtube playlist:%s, maxCount:%s" % (url, str(maxCount)) )
    # taskCount = cpu_count() -1
    # print("we have %d cpus" % (taskCount + 1))

    taskCount = DOWNLOAD_TASK_CUNT 

    pl = Playlist(url)
    pl.populate_video_urls()
    videoUrls = pl.video_urls
    if maxCount:
        videoUrls = videoUrls[0: maxCount: 1]
    elif start and end:
        videoUrls = videoUrls[start-1: end]
    elif start and end is None:
        videoUrls = videoUrls[start-1::]
    elif start is None and end:
        videoUrls = videoUrls[:end:]
    
    prefix_gen = pl._path_num_prefix_generator()

    playlistTitle = getPlaylistTitle(pl.construct_playlist_url())


    #single thread
    # for link in videoUrls:
    #     prefix = next(prefix_gen)
    #     print('file prefix is: %s' % prefix)
    #     downloadSingle(link, filename_prefix=prefix, subFolder=playlistTitle)


    # multiple thread
    argsArrayList = []
    for i in range(0, taskCount):
        argsArrayList.append([])

    i = 0
    for link in videoUrls:
        idx = i % taskCount
        i += 1
        prefix = next(prefix_gen)
        argsArrayList[idx].append((link, prefix, playlistTitle)) 
        s_linkStatusDic[link] = False


    downloadListMultipleThread(argsArrayList)
    times = 1
    while hasToDownloadTask():
        times += 1
        toDownloadFileDic = {k: v for k, v in s_linkStatusDic.items() if v == False}
        print("=>try %d times, file to download count: %d" % (times, len(toDownloadFileDic)))
        print(" %s", str(toDownloadFileDic))
        downloadListMultipleThread(argsArrayList)


    print("all download task done.")

def hasToDownloadTask():
    ret = False
    for key in s_linkStatusDic:
        if s_linkStatusDic[key] == False:
            ret = True
            break

    return ret

def downloadListMultipleThread(argsArrayList):
    downloadTasks = []
    for argsArray in argsArrayList:
        # downloadSingle(link, filename_prefix=prefix, subFolder=playlistTitle)
        downloadThreadFunc = ListDownloadThreadFunc(downloadSingle, argsArray, s_linkStatusDic)
        task = threading.Thread(target=downloadThreadFunc)
        downloadTasks.append(task)


    for task in downloadTasks:
        task.start()

    for task in downloadTasks:
        task.join()


def getPlaylistTitle(url):
    req = request.get(url)
    open_tag = "<title>"
    end_tag = "</title>"
    matchresult = re.compile(open_tag + "(.+?)" + end_tag)
    matchresult = matchresult.search(req).group()
    matchresult = matchresult.replace(open_tag, "")
    matchresult = matchresult.replace(end_tag, "")
    matchresult = matchresult.replace("- YouTube", "")
    matchresult = matchresult.strip()

    return matchresult


def init():
    mkdir(TEMP_FOLDER)
    mkdir(OUTPUT_FOLDER)

def doMain(url, maxCount=None, start=None, end=None):
    if "list=" in url:
        # list download video
        downloadList(url, maxCount, start, end)
        pass
    else:
        downloadSingle(url)


    print("well download")


def printUsage():
    print('''usage:
NOTE: PLEASE USE THIS SCRIPT IN Python 3.X
      AND You should INSTALL pytube by
        pip install pytube

	./ytd.py [YouTube url]

for example:
    single video download:
        python ytd.py "https://www.youtube.com/watch?v=VW5bBIA8AHY"
	    ./ytd "https://www.youtube.com/watch?v=VW5bBIA8AHY"
    list download:
        python ytd.py "https://www.youtube.com/watch?v=kclUtptKsT8&list=PLThYwnIoLwyXZr0xQHMfEZcoYPXWtTVJO&index=2&t=11s"
        python ytd.py "https://www.youtube.com/watch?v=kclUtptKsT8&list=PLThYwnIoLwyXZr0xQHMfEZcoYPXWtTVJO&index=2&t=11s" -c 10
        python ytd.py "https://www.youtube.com/watch?v=kclUtptKsT8&list=PLThYwnIoLwyXZr0xQHMfEZcoYPXWtTVJO&index=2&t=11s" --scope 1,10
        python ytd.py "https://www.youtube.com/playlist?list=PLwmPBqRou8AOb_RPjM4gwTqPkzmXcpQB8" -c 56
        ./ytd "https://www.youtube.com/watch?v=kclUtptKsT8&list=PLThYwnIoLwyXZr0xQHMfEZcoYPXWtTVJO&index=1"

''')

# ------------------------ main ------------------------
if __name__ == '__main__':
    length = len(sys.argv)
    print(sys.argv)

    init()

    if length == 1:
        # mini video
        # doMain('https://www.youtube.com/watch?v=VW5bBIA8AHY')
        #durm
        # doMain('https://www.youtube.com/watch?v=kclUtptKsT8')
        #doMain('https://www.youtube.com/watch?v=kclUtptKsT8&list=PLThYwnIoLwyXZr0xQHMfEZcoYPXWtTVJO&index=2&t=11s')
        printUsage()

    elif length == 2:
        if sys.argv[1] == "-h":
            printUsage()
        else:
            doMain(sys.argv[1])

    elif length == 4:
        if sys.argv[2] == '-c':
            # downlaod by max count
            maxCount = int(sys.argv[3])
            doMain(sys.argv[1], maxCount)
        if sys.args[2] == "--scope":
            scopeStr = sys.argv[3].split(",")
            doMain(sys.argv[1], start=int(scopeStr[0]), end=int(scopeStr[1]))
        
    else:
        printUsage()
