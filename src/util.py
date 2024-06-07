import os

def makeDirIfNotExist(path):
    if not os.path.exists(path):
        os.makedirs(path)
