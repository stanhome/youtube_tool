#!/usr/bin/env python
# coding=utf-8
# @brief: Youtube download
# @author: stan
# @date: 20190531

import os, traceback, sys, subprocess
import subprocess
import threading
import re
from string import Template
from pytube import YouTube, Playlist, request
from MyThread import MyThread

ITAG_1080P_WEBM = 248
ITAG_1080P_MP4 = 137


CWD = os.getcwd()
TEMP_FOLDER = os.path.join(CWD, "temp")
OUTPUT_FOLDER = os.path.join(CWD, "output")
FFMPEGE_FILE_PATH = os.path.join(CWD, "ffmpeg")
CMD_FFMPEGE_TPL = Template(FFMPEGE_FILE_PATH + ' -y -i "${video}" -i "${audio}" "${out_file_name}.mp4"  -c:v libx264 -c:a aac')


def mkdir(path):
    # uPath = path.decode("utf-8")
    folder = os.path.exists(path)
    if not folder:
        os.makedirs(path)
    

def printUsage():
    print('''usage:
NOTE: PLEASE USE THIS SCRIPT IN Python 3.X
      AND You should INSTALL pytube by
        pip install pytube

	./ytd.py [YouTube url]

for example:
    single video download:
	    ./ytd https://www.youtube.com/watch?v=VW5bBIA8AHY
    list download:
        ./ytd https://www.youtube.com/watch?v=kclUtptKsT8&list=PLThYwnIoLwyXZr0xQHMfEZcoYPXWtTVJO&index=1

''')

def downloadSingle(url, filename_prefix=None, subFolder=None):
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


    # 1. start download video
    videoToDownloadStream = yt.streams.get_by_itag(ITAG_1080P_WEBM)
    if videoToDownloadStream is None:
        videoToDownloadStream = yt.streams.get_by_itag(ITAG_1080P_MP4)
    if videoToDownloadStream is None:
        print("[e] 1080p video srouce not found.")

    # single thread
    # print("download video stream(%s), size(%f MB) to save:%s" % (str(videoToDownloadStream), videoToDownloadStream.filesize / 1048576.0, videoToDownloadStream.default_filename))
    # videoFilePath = videoToDownloadStream.download(output_path=TEMP_FOLDER, filename=None, filename_prefix="v_")
    # print("download done: %s" % videoFilePath)

    # multiple thread
    videoTip = "download video stream(%s), size(%f MB) to save:%s" % (str(videoToDownloadStream), videoToDownloadStream.filesize / 1048576.0, videoToDownloadStream.default_filename)
    videoDownloadTask = MyThread(videoToDownloadStream.download, 
        {"output_path": TEMP_FOLDER, "filename": None, "filename_prefix": "v_"},
        videoTip)

    videoDownloadTask.start()


    # 2. start download audio
    audioToDownloadStream = yt.streams.filter(only_audio=True).order_by("abr").desc().first()
    # single thread
    print("download audio stream(%s), size(%f MB) to save: %s" % (str(audioToDownloadStream), audioToDownloadStream.filesize / 1048576.0, audioToDownloadStream.default_filename))
    audioFilePath = audioToDownloadStream.download(output_path=TEMP_FOLDER, filename_prefix='a_')
    print("download done: %s" % audioFilePath)

    # multiple thread( let audio download task in main task)
    # tip = "download audio stream(%s), size(%f MB) to save: %s" % (str(audioToDownloadStream), audioToDownloadStream.filesize / 1048576.0, audioToDownloadStream.default_filename)
    # audioDownloadTask = MyThread(audioToDownloadStream.download, 
    #     {"output_path":TEMP_FOLDER, "filename_prefix":"a_"}, 
    #     tip)
    # audioDownloadTask.start()


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
    videoDownloadTask.join()
    videoFilePath = videoDownloadTask.getResult()


    # 5. merge video and audio
    # ffmpeg -y -i %video% -i %audio% "output_file.mp4"  -c:v libx264 -c:a aac
    mergedCmd = CMD_FFMPEGE_TPL.substitute(video=videoFilePath, audio=audioFilePath, out_file_name=outputFileName)
    print(mergedCmd)
    # p = subprocess.Popen(mergedCmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    p = subprocess.Popen(mergedCmd)
    while p.poll() is None:
        pass
        # line = p.stdout.readline()
        # line = line.strip()
        # if line:
        #     print("[ffmpeg]:" + line)

    if p.returncode == 0:
        print("%s.mp4 merged success" % (fileName))
    else:
        print("[e]may be merged failed.")

    print("well download")


def downloadList(url):
    pl = Playlist(url)
    pl.populate_video_urls()
    videoUrls = pl.video_urls
    prefix_gen = pl._path_num_prefix_generator()

    playlistTitle = getPlaylistTitle(pl.construct_playlist_url())

    # TODO: creat list folder 
    for link in videoUrls:
        prefix = next(prefix_gen)
        print('file prefix is: %d' % prefix)
        downloadSingle(link, filename_prefix=prefix, subFolder=playlistTitle)

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


def doMain(url):
    if "list=" in url:
        # list download video
        downloadList(url)
        pass
    else:
        downloadSingle(url)
    pass


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
        doMain('https://www.youtube.com/watch?v=kclUtptKsT8&list=PLThYwnIoLwyXZr0xQHMfEZcoYPXWtTVJO&index=2&t=11s')
        # printUsage()

    elif length == 2:
        if sys.argv[1] == "-h":
            printUsage()
        else:
            doMain(sys.argv[1])
    else:
        printUsage()
