import numpy as np


def Hikcam_callback(camnum: int, im: np.ndarray):
    print("[INFO] My Callback: Cam {}, frame {}".format(camnum, im.shape))
    # TODO 统计帧率
    # TODO 添加功能
    return im
