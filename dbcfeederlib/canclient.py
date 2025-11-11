from ctypes import *

import time
import os
import logging
from typing import Optional
import can  # type: ignore
import sys
import struct
import typing

log = logging.getLogger(__name__)

# Lấy đường dẫn tuyệt đối tới file .so
so_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'libcontrolcanfd.so'))
VCI_USBCAN2 = 41
STATUS_OK = 1
INVALID_DEVICE_HANDLE  = 0
INVALID_CHANNEL_HANDLE = 0
TYPE_CAN = 0
TYPE_CANFD = 1

class VCI_INIT_CONFIG(Structure):  
    _fields_ = [("AccCode", c_uint),
                ("AccMask", c_uint),
                ("Reserved", c_uint),
                ("Filter", c_ubyte),
                ("Timing0", c_ubyte),
                ("Timing1", c_ubyte),
                ("Mode", c_ubyte)
                ]  

class VCI_CAN_OBJ(Structure):  
    _fields_ = [("ID", c_uint),
                ("TimeStamp", c_uint),
                ("TimeFlag", c_ubyte),
                ("SendType", c_ubyte),
                ("RemoteFlag", c_ubyte),
                ("ExternFlag", c_ubyte),
                ("DataLen", c_ubyte),
                ("Data", c_ubyte*8),
                ("Reserved", c_ubyte*3)
                ] 

class _ZCAN_CHANNEL_CAN_INIT_CONFIG(Structure):
    _fields_ = [("acc_code", c_uint),
                ("acc_mask", c_uint),
                ("reserved", c_uint),
                ("filter",   c_ubyte),
                ("timing0",  c_ubyte),
                ("timing1",  c_ubyte),
                ("mode",     c_ubyte)]

class _ZCAN_CHANNEL_CANFD_INIT_CONFIG(Structure):
    _fields_ = [("acc_code",     c_uint),
                ("acc_mask",     c_uint),
                ("abit_timing",  c_uint),
                ("dbit_timing",  c_uint),
                ("brp",          c_uint),
                ("filter",       c_ubyte),
                ("mode",         c_ubyte),
                ("pad",          c_ushort),
                ("reserved",     c_uint)]

class _ZCAN_CHANNEL_INIT_CONFIG(Union):
    _fields_ = [("can", _ZCAN_CHANNEL_CAN_INIT_CONFIG), ("canfd", _ZCAN_CHANNEL_CANFD_INIT_CONFIG)]

class ZCAN_CHANNEL_INIT_CONFIG(Structure):
    _fields_ = [("can_type", c_uint),
                ("config", _ZCAN_CHANNEL_INIT_CONFIG)]

class ZCAN_CAN_FRAME(Structure):
    _fields_ = [("can_id",  c_uint, 29),
                ("err",     c_uint, 1),
                ("rtr",     c_uint, 1),
                ("eff",     c_uint, 1), 
                ("can_dlc", c_ubyte),
                ("__pad",   c_ubyte),
                ("__res0",  c_ubyte),
                ("__res1",  c_ubyte),
                ("data",    c_ubyte * 8)]

class ZCAN_CANFD_FRAME(Structure):
    _fields_ = [("can_id", c_uint, 29), 
                ("err",    c_uint, 1),
                ("rtr",    c_uint, 1),
                ("eff",    c_uint, 1), 
                ("len",    c_ubyte),
                ("brs",    c_ubyte, 1),
                ("esi",    c_ubyte, 1),
                ("__res",  c_ubyte, 6),
                ("__res0", c_ubyte),
                ("__res1", c_ubyte),
                ("data",   c_ubyte * 64)]

class ZCAN_Transmit_Data(Structure):
    _fields_ = [("frame", ZCAN_CAN_FRAME), ("transmit_type", c_uint)]

class ZCAN_Receive_Data(Structure):
    _fields_  = [("frame", ZCAN_CAN_FRAME), ("timestamp", c_ulonglong)]

class ZCAN_TransmitFD_Data(Structure):
    _fields_ = [("frame", ZCAN_CANFD_FRAME), ("transmit_type", c_uint)]

class ZCAN_ReceiveFD_Data(Structure):
    _fields_ = [("frame", ZCAN_CANFD_FRAME), ("timestamp", c_ulonglong)]

# CanDLLName = 'libcontrolcanfd.so'
canDLL = cdll.LoadLibrary(so_path)

# Define function argument and return types
canDLL.ZCAN_OpenDevice.restype = c_void_p
canDLL.ZCAN_SetAbitBaud.argtypes = (c_void_p, c_ulong, c_ulong)
canDLL.ZCAN_SetDbitBaud.argtypes = (c_void_p, c_ulong, c_ulong)
canDLL.ZCAN_SetCANFDStandard.argtypes = (c_void_p, c_ulong, c_ulong)
canDLL.ZCAN_InitCAN.argtypes = (c_void_p, c_ulong, c_void_p)
canDLL.ZCAN_InitCAN.restype = c_void_p
canDLL.ZCAN_StartCAN.argtypes = (c_void_p,)
canDLL.ZCAN_Transmit.argtypes = (c_void_p, c_void_p, c_ulong)
canDLL.ZCAN_TransmitFD.argtypes = (c_void_p, c_void_p, c_ulong)
canDLL.ZCAN_GetReceiveNum.argtypes = (c_void_p, c_ulong)
canDLL.ZCAN_Receive.argtypes = (c_void_p, c_void_p, c_ulong, c_long)
canDLL.ZCAN_ReceiveFD.argtypes = (c_void_p, c_void_p, c_ulong, c_long)
canDLL.ZCAN_ResetCAN.argtypes = (c_void_p,)
canDLL.ZCAN_CloseDevice.argtypes = (c_void_p,)

canDLL.ZCAN_ClearFilter.argtypes = (c_void_p,)
canDLL.ZCAN_AckFilter.argtypes = (c_void_p,)
canDLL.ZCAN_SetFilterMode.argtypes = (c_void_p, c_ulong)
canDLL.ZCAN_SetFilterStartID.argtypes = (c_void_p, c_ulong)
canDLL.ZCAN_SetFilterEndID.argtypes = (c_void_p, c_ulong)

def open_device():
    m_dev = canDLL.ZCAN_OpenDevice(VCI_USBCAN2, 0, 0)
    if m_dev == INVALID_DEVICE_HANDLE:
        print("Open Device failed!")
    return m_dev

def set_baud_rate(device_handle):
    # Set baud rate for CAN0 and CAN1
    baud_rate_a = 500000
    baud_rate_d = 1000000
    for channel in range(2):
        ret = canDLL.ZCAN_SetAbitBaud(device_handle, channel, baud_rate_a)
        if ret != STATUS_OK:
            print(f"Set CAN{channel} abit:{baud_rate_a} failed!")
        print(f"Set CAN{channel} abit:{baud_rate_a} OK!")
        ret = canDLL.ZCAN_SetDbitBaud(device_handle, channel, baud_rate_d)
        if ret != STATUS_OK:
            print(f"Set CAN{channel} dbit:{baud_rate_d} failed!")
        print(f"Set CAN{channel} dbit:{baud_rate_d} OK!")

def configure_canfd_mode(device_handle):
    for channel in range(2):
        ret = canDLL.ZCAN_SetCANFDStandard(device_handle, channel, 0)
        if ret != STATUS_OK:
            print(f"Set CAN{channel} ISO mode failed!")
        print(f"Set CAN{channel} ISO mode OK!")

def init_channel(device_handle, channel):
    init_config = ZCAN_CHANNEL_INIT_CONFIG()
    init_config.can_type = TYPE_CANFD
    init_config.config.canfd.mode = 0
    dev_ch = canDLL.ZCAN_InitCAN(device_handle, channel, byref(init_config))
    if dev_ch == INVALID_CHANNEL_HANDLE:
        print(f"Init CAN{channel} failed!")
    print(f"Init CAN{channel} OK!")
    return dev_ch

def start_channel(dev_ch):
    ret = canDLL.ZCAN_StartCAN(dev_ch)
    if ret != STATUS_OK:
        print(f"Start CAN channel failed!")
    print("Start CAN channel OK!")

def configure_filter(dev_ch2):
    canDLL.ZCAN_ClearFilter(dev_ch2)
    canDLL.ZCAN_SetFilterMode(dev_ch2, 1)
    #canDLL.ZCAN_SetFilterStartID(dev_ch2, 5)
    #canDLL.ZCAN_SetFilterEndID(dev_ch2, 6)
    canDLL.ZCAN_AckFilter(dev_ch2)

def send_canfd_data(dev_ch1):
    transmit_canfd_num = 10
    canfd_msgs = (ZCAN_TransmitFD_Data * transmit_canfd_num)()
    for i in range(transmit_canfd_num):
        canfd_msgs[i].transmit_type = 0
        canfd_msgs[i].frame.eff     = 1
        canfd_msgs[i].frame.rtr     = 0
        canfd_msgs[i].frame.brs     = 1
        canfd_msgs[i].frame.can_id  = i
        canfd_msgs[i].frame.len     = 16
        for j in range(canfd_msgs[i].frame.len):
            canfd_msgs[i].frame.data[j] = j
    ret = canDLL.ZCAN_TransmitFD(dev_ch1, canfd_msgs, transmit_canfd_num)
    print(f"\nCAN0 Transmit CANFD Num: {ret}.")

def receive_canfd_data(dev_ch2):
    ret = canDLL.ZCAN_GetReceiveNum(dev_ch2, TYPE_CANFD)
    while ret <= 0:
        time.sleep(0.01)  # Add a small delay to avoid busy-waiting
        ret = canDLL.ZCAN_GetReceiveNum(dev_ch2, TYPE_CANFD)
        #print(ret)
    if ret > 0:
        rcv_canfd_msgs = (ZCAN_ReceiveFD_Data * ret)()
        num = canDLL.ZCAN_ReceiveFD(dev_ch2, byref(rcv_canfd_msgs), ret, -1)
        print(f"CAN1 Received CANFD NUM: {num}.")
        for i in range(num):
            print(f"[{i}]:ts:{rcv_canfd_msgs[i].timestamp}, id:{rcv_canfd_msgs[i].frame.can_id}, len:{rcv_canfd_msgs[i].frame.len}, "
                  f"eff:{rcv_canfd_msgs[i].frame.eff}, rtr:{rcv_canfd_msgs[i].frame.rtr}, esi:{rcv_canfd_msgs[i].frame.esi}, "
                  f"brs:{rcv_canfd_msgs[i].frame.brs}, data:{' '.join(str(rcv_canfd_msgs[i].frame.data[j]) for j in range(rcv_canfd_msgs[i].frame.len))}")
# IsElectricalPowertrainEngaged
def send_can_data(dev_ch1, can_id, can_data):
    # if type(data)==str():
    #     transmit_can_num = len(data)
    # else:
    #     transmit_can_num = data
    # print(type(data)==str())
    # print(type(transmit_can_num))
    # print(data, threshold)
    datalength = 5
    transmit_can_num = datalength*2
    can_msgs = (ZCAN_Transmit_Data * transmit_can_num)()
    id = hex(can_id)
    for i in range(transmit_can_num):
        can_msgs[i].transmit_type = 0
        can_msgs[i].frame.eff     = 0
        can_msgs[i].frame.rtr     = 0
        can_msgs[i].frame.can_id  = can_id
        can_msgs[i].frame.can_dlc = datalength
        for j in range(can_msgs[i].frame.can_dlc):
            # can_msgs[i].frame.data[j] = j
            ### Begin Byte[i]
            can_msgs[i].frame.data[j] = can_data[j]

    ret = canDLL.ZCAN_Transmit(dev_ch1, can_msgs, 1)
    print(f"\nCAN0 Transmit CAN Num: {ret} {transmit_can_num}")

def receive_can_data(dev_ch2):
    while True:
        ret = canDLL.ZCAN_GetReceiveNum(dev_ch2, TYPE_CAN)
        while ret <= 0:
            time.sleep(0.01)  # Add a small delay to avoid busy-waiting
            ret = canDLL.ZCAN_GetReceiveNum(dev_ch2, TYPE_CAN)
        if ret > 0:
            rcv_can_msgs = (ZCAN_Receive_Data * ret)()
            num = canDLL.ZCAN_Receive(dev_ch2, byref(rcv_can_msgs), ret, -1)
            # for i in range(num):
            #     print(f"[{i}]:ts:{rcv_can_msgs[i].timestamp}, id:{rcv_can_msgs[i].frame.can_id}, len:{rcv_can_msgs[i].frame.can_dlc}, "
            #         f"eff:{rcv_can_msgs[i].frame.eff}, rtr:{rcv_can_msgs[i].frame.rtr}, "
            #         f"data:{' '.join(str(rcv_can_msgs[i].frame.data[j]) for j in range(rcv_can_msgs[i].frame.can_dlc))}")
        return rcv_can_msgs

def close_device(dev_ch1, dev_ch2, device_handle):
    ret = canDLL.ZCAN_ResetCAN(dev_ch1)
    if ret != STATUS_OK:
        print("Close CAN0 failed!")
    print("Close CAN0 OK!")    
    ret = canDLL.ZCAN_ResetCAN(dev_ch2)
    if ret != STATUS_OK:
        print("Close CAN1 failed!")
    print("Close CAN1 OK!")    
    ret = canDLL.ZCAN_CloseDevice(device_handle)
    if ret != STATUS_OK:
        print("Close Device failed!")
    print("Close Device OK!")



class CANMessage:
    def __init__(self, msg: can.Message):
        self.msg = msg

    def get_arbitration_id(self) -> int:
        """Get arbitration/frame id of message"""
        return self.msg.arbitration_id

    def get_data(self):
        """Get message data"""
        return self.msg.data

def send_a(dev_ch, arbitration_id, data):
    """Write message to CAN bus."""
    # Version with odler usb - sendcan
    msg = can.Message(arbitration_id=arbitration_id, data=data)
    
    try:
        send_can_data(dev_ch1=dev_ch,can_id=msg.arbitration_id, can_data=msg.data)
        print("Send CAN msg: %s, %s", msg.arbitration_id, msg.data)
        # if log.isEnabledFor(logging.DEBUG):
        #     log.debug("Sent message [channel: %s]: %s", self._bus.channel_info, msg)
    except can.CanError:
        print("Failed to send message via CAN bus")

device_handle = open_device()
set_baud_rate(device_handle)
configure_canfd_mode(device_handle)
    
dev_ch1 = init_channel(device_handle, 0)
start_channel(dev_ch1)
    
dev_ch2 = init_channel(device_handle, 1)
configure_filter(dev_ch2)
start_channel(dev_ch2)
    # executor = ThreadPoolExecutor(3)


class CANClient:


    def __init__(self, *args, **kwargs):
        log.info("Start init CAN USB Client")
        '''
            device_handle = open_device()
    set_baud_rate(device_handle)
    configure_canfd_mode(device_handle)
    
    dev_ch1 = init_channel(device_handle, 0)
    start_channel(dev_ch1)
    
    dev_ch2 = init_channel(device_handle, 1)
    configure_filter(dev_ch2)
    start_channel(dev_ch2)
    # executor = ThreadPoolExecutor(3)


    send(dev_ch=dev_ch2,arbitration_id=CAN_msg.get_arbitration_id(), data=CAN_msg.get_data())
    print("Send CAN msg: %s, %s", CAN_msg.get_arbitration_id(), CAN_msg.get_data())
        '''
        
        # self.device_handle = open_device()
        # set_baud_rate(self.device_handle)
        # configure_canfd_mode(self.device_handle)
        
        # self.dev_ch1 = init_channel(self.device_handle, 0)
        # start_channel(self.dev_ch1)
        
        # self.dev_ch2 = init_channel(self.device_handle, 1)
        # configure_filter(self.dev_ch2)
        # start_channel(self.dev_ch2)
            

    def stop(self):
        """Shut down CAN bus."""
        # self._bus.shutdown()
        close_device(dev_ch1=dev_ch1, dev_ch2=dev_ch2, device_handle=device_handle)
        log.info("Close USB CAN !!!")


    def recv(self, timeout: int = 1) -> Optional[CANMessage]:
        """Receive message from CAN bus."""
        print(timeout)
        try:
            rcv_can_msgs = receive_can_data(dev_ch2)
            i = 0
            # log.info("DATA TYPE: ID datatypes: %s   -- Data: %s", type(rcv_can_msgs[i].frame.can_id), type(rcv_can_msgs[i].frame.data[0]))
            log.info("Receive CAN message from USB CAN: ID %s Data: %s", rcv_can_msgs[i].frame.can_id, rcv_can_msgs[i].frame.data[0])
        except can.CanError:
            rcv_can_msgs = None  
            if dev_ch2:
                log.error("Error while waiting for recv from CAN", exc_info=True)
            else:
                # This is expected if we are shutting down 
                log.debug("Exception received during shutdown")
                
        i = 0
        if rcv_can_msgs:
            canmsg_format = can.Message(timestamp=rcv_can_msgs[i].timestamp, arbitration_id=rcv_can_msgs[i].frame.can_id, data=rcv_can_msgs[i].frame.data)
            canmsg = CANMessage(canmsg_format)
            # log.info("Type ID: %s - Type Data: %s", type(canmsg.get_arbitration_id()), type(canmsg.get_data()))
            log.info("Convert to CAN msg STRUCT: [ID] %s - [data] %s", canmsg.get_arbitration_id(), canmsg.get_data())
            return canmsg
        return None



    def send(self, arbitration_id, data):
        """Write message to CAN bus."""
        """
            can_data = bytearray([0x02, 0x00, 0x00, 0x00, 0x00])
    can_id = 1281
    can_msg = can.Message(arbitration_id=can_id, data=can_data)
    CAN_msg = CANMessage(can_msg)


    send_can_data(dev_ch1=dev_ch2, can_id = CAN_msg.get_arbitration_id(), can_data = CAN_msg.get_data())
        """
        in_id = arbitration_id
        in_data = data
        log.info("[before send] Type of ID: %s - Type Data: %s", type(in_id), type(in_data))
        log.info("Expected: int - bytearray")
        in_data = bytearray(in_data)
        msg = can.Message(arbitration_id=in_id, data=in_data)
        log.info("[After format to can.Message] Type of ID: %s - Type Data: %s", type(msg.arbitration_id), type(msg.data))
        CAN_msg = CANMessage(msg)
        send_can_data(dev_ch1=dev_ch2, can_id = CAN_msg.get_arbitration_id(), can_data = CAN_msg.get_data())
        send_a(dev_ch=dev_ch2,arbitration_id=CAN_msg.get_arbitration_id(), data=CAN_msg.get_data())
        # log.info("[After format to CANMessage] Type of ID: %s - Type Data: %s", type(CAN_msg.get_arbitration_id()), type(CAN_msg.get_data()))
        # log.info("[After format to CANMessage] ID: %s - Data: %s", CAN_msg.get_arbitration_id(), CAN_msg.get_data())

        # try:
        #     send_a(dev_ch=self.dev_ch2,arbitration_id=CAN_msg.get_arbitration_id(), data=CAN_msg.get_data())
        #     log.info("[After Send] CAN msg: %s, %s", CAN_msg.get_arbitration_id(), CAN_msg.get_data())
        # except can.CanError:
        #     log.error("Failed to send message via CAN bus")
