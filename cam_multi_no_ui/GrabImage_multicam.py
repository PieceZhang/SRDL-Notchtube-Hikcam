# -- coding: utf-8 --

import sys
import threading
import msvcrt

from ctypes import *

sys.path.append("../MvImport")
from MvImport.MvCameraControl_class import *

g_bExit = False

from My_utils.utils_callback import Hikcam_callback
import numpy as np


# 彩色图像转为python数组
def Color_numpy(data, nWidth, nHeight):
    data_ = np.frombuffer(data, count=int(nWidth * nHeight * 3), dtype=np.uint8, offset=0)
    data_r = data_[0:nWidth * nHeight * 3:3]
    data_g = data_[1:nWidth * nHeight * 3:3]
    data_b = data_[2:nWidth * nHeight * 3:3]

    data_r_arr = data_r.reshape(nHeight, nWidth)
    data_g_arr = data_g.reshape(nHeight, nWidth)
    data_b_arr = data_b.reshape(nHeight, nWidth)
    numArray = np.zeros([nHeight, nWidth, 3], "uint8")

    numArray[:, :, 0] = data_r_arr
    numArray[:, :, 1] = data_g_arr
    numArray[:, :, 2] = data_b_arr
    return numArray


# 为线程定义一个函数
def work_thread(caml, pData=0, nDataSize=0):
    stOutFrame = MV_FRAME_OUT()
    buf_cache = None
    img_buff = None
    memset(byref(stOutFrame), 0, sizeof(stOutFrame))
    while True:
        for index, cam in enumerate(caml):
            ret = cam.MV_CC_GetImageBuffer(stOutFrame, 2000)
            if None != stOutFrame.pBufAddr and 0 == ret:
                print("[INFO: CAM%d] Thread: get one frame: Width[%d], Height[%d], nFrameNum[%d]" % (
                    index, stOutFrame.stFrameInfo.nWidth, stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nFrameNum))
                nRet = cam.MV_CC_FreeImageBuffer(stOutFrame)

                if None == buf_cache:
                    buf_cache = (c_ubyte * stOutFrame.stFrameInfo.nFrameLen)()
                cdll.msvcrt.memcpy(byref(buf_cache), stOutFrame.pBufAddr, stOutFrame.stFrameInfo.nFrameLen)
                n_save_image_size = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight * 3 + 2048
                if img_buff is None:
                    img_buff = (c_ubyte * n_save_image_size)()

            else:
                print("no data[0x%x]" % ret)

            """-------------------------------------------------------------------------"""
            # 转换像素结构体赋值
            stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
            memset(byref(stConvertParam), 0, sizeof(stConvertParam))
            stConvertParam.nWidth = stOutFrame.stFrameInfo.nWidth
            stConvertParam.nHeight = stOutFrame.stFrameInfo.nHeight
            stConvertParam.pSrcData = cast(buf_cache, POINTER(c_ubyte))
            stConvertParam.nSrcDataLen = stOutFrame.stFrameInfo.nFrameLen
            stConvertParam.enSrcPixelType = stOutFrame.stFrameInfo.enPixelType

            # RGB直接显示
            if PixelType_Gvsp_RGB8_Packed == stOutFrame.stFrameInfo.enPixelType:
                numArray = Color_numpy(buf_cache, stOutFrame.stFrameInfo.nWidth, stOutFrame.stFrameInfo.nHeight)
            else:
                nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight * 3
                stConvertParam.enDstPixelType = PixelType_Gvsp_RGB8_Packed
                stConvertParam.pDstBuffer = (c_ubyte * nConvertSize)()
                stConvertParam.nDstBufferSize = nConvertSize
                ret = cam.MV_CC_ConvertPixelType(stConvertParam)
                if ret != 0:
                    continue
                cdll.msvcrt.memcpy(byref(img_buff), stConvertParam.pDstBuffer, nConvertSize)
                numArray = Color_numpy(img_buff, stOutFrame.stFrameInfo.nWidth, stOutFrame.stFrameInfo.nHeight)

            """ Add callback here """
            numArray, status = Hikcam_callback(index, numArray)
            if status is False or g_bExit is True:
                cam_deinit(caml)
                sys.exit()
            """-------------------------------------------------------------------------"""


def cam_init(cnlist):
    caml = []
    for nConnectionNum in cnlist:
        # ch:创建相机实例 | en:Creat Camera Object
        cami = MvCamera()

        # ch:选择设备并创建句柄 | en:Select device and create handle
        stDeviceList = cast(deviceList.pDeviceInfo[int(nConnectionNum)], POINTER(MV_CC_DEVICE_INFO)).contents

        ret = cami.MV_CC_CreateHandle(stDeviceList)
        if ret != 0:
            print("create handle fail! ret[0x%x]" % ret)
            sys.exit()

        # ch:打开设备 | en:Open device
        ret = cami.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        if ret != 0:
            print("open device fail! ret[0x%x]" % ret)
            sys.exit()

        # ch:探测网络最佳包大小(只对GigE相机有效) | en:Detection network optimal package size(It only works for the GigE camera)
        if stDeviceList.nTLayerType == MV_GIGE_DEVICE:
            nPacketSize = cami.MV_CC_GetOptimalPacketSize()
            if int(nPacketSize) > 0:
                ret = cami.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
                if ret != 0:
                    print("Warning: Set Packet Size fail! ret[0x%x]" % ret)
            else:
                print("Warning: Get Packet Size fail! ret[0x%x]" % nPacketSize)

        stBool = c_bool(False)
        ret = cami.MV_CC_GetBoolValue("AcquisitionFrameRateEnable", stBool)
        if ret != 0:
            print("get AcquisitionFrameRateEnable fail! ret[0x%x]" % ret)

        # ch:设置触发模式为off | en:Set trigger mode as off
        ret = cami.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
        if ret != 0:
            print("set trigger mode fail! ret[0x%x]" % ret)
            sys.exit()

        # ch:开始取流 | en:Start grab image
        ret = cami.MV_CC_StartGrabbing()
        if ret != 0:
            print("start grabbing fail! ret[0x%x]" % ret)
            sys.exit()

        caml.append(cami)

    return caml


def cam_deinit(caml):
    for cam in caml:
        # ch:停止取流 | en:Stop grab image
        ret = cam.MV_CC_StopGrabbing()
        if ret != 0:
            print("stop grabbing fail! ret[0x%x]" % ret)
            sys.exit()

        # ch:关闭设备 | Close device
        ret = cam.MV_CC_CloseDevice()
        if ret != 0:
            print("close deivce fail! ret[0x%x]" % ret)
            sys.exit()

        # ch:销毁句柄 | Destroy handle
        ret = cam.MV_CC_DestroyHandle()
        if ret != 0:
            print("destroy handle fail! ret[0x%x]" % ret)
            sys.exit()


if __name__ == "__main__":

    deviceList = MV_CC_DEVICE_INFO_LIST()
    tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE

    # ch:枚举设备 | en:Enum device
    ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
    if ret != 0:
        print("enum devices fail! ret[0x%x]" % ret)
        sys.exit()

    if deviceList.nDeviceNum == 0:
        print("find no device!")
        sys.exit()

    print("Find %d devices!" % deviceList.nDeviceNum)

    for i in range(0, deviceList.nDeviceNum):
        mvcc_dev_info = cast(deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
        if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
            print("\ngige device: [%d]" % i)
            strModeName = ""
            for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName:
                strModeName = strModeName + chr(per)
            print("device model name: %s" % strModeName)

            nip1 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xff000000) >> 24)
            nip2 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00ff0000) >> 16)
            nip3 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000ff00) >> 8)
            nip4 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000ff)
            print("current ip: %d.%d.%d.%d\n" % (nip1, nip2, nip3, nip4))
        elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
            print("\nu3v device: [%d]" % i)
            strModeName = ""
            for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName:
                if per == 0:
                    break
                strModeName = strModeName + chr(per)
            print("device model name: %s" % strModeName)

            strSerialNumber = ""
            for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                if per == 0:
                    break
                strSerialNumber = strSerialNumber + chr(per)
            print("user serial number: %s" % strSerialNumber)

    # nConnectionNum = input("please input the number of the device to connect:")
    #
    # if int(nConnectionNum) >= deviceList.nDeviceNum:
    #     print("intput error!")
    #     sys.exit()

    # 检测所有cam
    camnumlist = list(range(0, deviceList.nDeviceNum))

    # camlist: 包含完成初始化后的cam实例
    camlist = cam_init(camnumlist)

    try:
        hThreadHandle = threading.Thread(target=work_thread, args=(camlist, None, None))
        hThreadHandle.start()
    except:
        print("error: unable to start thread")
        sys.exit()

    print("press a key to stop grabbing.")
    msvcrt.getch()

    g_bExit = True
    hThreadHandle.join()
