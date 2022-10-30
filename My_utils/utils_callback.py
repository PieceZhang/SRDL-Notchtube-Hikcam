import numpy as np
import cv2


def Hikcam_callback(camnum: int, im: np.ndarray):
    # TODO 统计帧率
    # TODO 添加功能
    print("[INFO: CAM{}] My Callback: Cam {}, frame {}".format(camnum, camnum, im.shape))
    cv2.imshow("camera{}".format(camnum), cv2.resize(im, (300, 200), interpolation=cv2.INTER_CUBIC))
    key = cv2.waitKey(1)
    if key == ord("q"):
        return im, False
    return im, True
