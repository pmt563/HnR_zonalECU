from ctypes import *
from kuksa_client.grpc import VSSClient, Datapoint
import time
import argparse

# ===========================================
# ARGUMENT PARSER
# ===========================================
parser = argparse.ArgumentParser(description='Send CAN ID 0x58A test frames')
parser.add_argument('-loopback', type=int, choices=[0, 1], default=0,
                    help='Enable CAN loopback mode (1=on, 0=off)')
parser.add_argument('databroker', nargs='?', default='127.0.0.1:55555',
                    help='Databroker address in IP:PORT format')
args = parser.parse_args()

# Parse IP and port
if ':' not in args.databroker:
    print("Invalid databroker format. Use IP:PORT (e.g., 127.0.0.1:55555)")
    exit(1)
databroker_ip, databroker_port = args.databroker.split(':', 1)
databroker_port = int(databroker_port)

# ===========================================
# CONSTANTS & STRUCTS
# ===========================================
VCI_USBCAN2 = 41
STATUS_OK = 1
INVALID_DEVICE_HANDLE = 0
INVALID_CHANNEL_HANDLE = 0
TYPE_CANFD = 1

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
    _fields_ = [("canfd", _ZCAN_CHANNEL_CANFD_INIT_CONFIG)]

class ZCAN_CHANNEL_INIT_CONFIG(Structure):
    _fields_ = [("can_type", c_uint),
                ("config", _ZCAN_CHANNEL_INIT_CONFIG)]

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

class ZCAN_TransmitFD_Data(Structure):
    _fields_ = [("frame", ZCAN_CANFD_FRAME), ("transmit_type", c_uint)]

class ZCAN_ReceiveFD_Data(Structure):
    _fields_ = [("frame", ZCAN_CANFD_FRAME), ("timestamp", c_ulonglong)]

# ===========================================
# LOAD DRIVER
# ===========================================
CanDLLName = './libcontrolcanfd.so'
canDLL = cdll.LoadLibrary(CanDLLName)
print('########################################################')
print('##   Chuang Xin USBCANFD Python Loopback Test v1.0   ###')
print('########################################################')

# Function prototypes
canDLL.ZCAN_OpenDevice.restype = c_void_p
canDLL.ZCAN_SetAbitBaud.argtypes = (c_void_p, c_ulong, c_ulong)
canDLL.ZCAN_SetDbitBaud.argtypes = (c_void_p, c_ulong, c_ulong)
canDLL.ZCAN_SetCANFDStandard.argtypes = (c_void_p, c_ulong, c_ulong)
canDLL.ZCAN_InitCAN.argtypes = (c_void_p, c_ulong, c_void_p)
canDLL.ZCAN_InitCAN.restype = c_void_p
canDLL.ZCAN_StartCAN.argtypes = (c_void_p,)
canDLL.ZCAN_TransmitFD.argtypes = (c_void_p, c_void_p, c_ulong)
canDLL.ZCAN_GetReceiveNum.argtypes = (c_void_p, c_ulong)
canDLL.ZCAN_ReceiveFD.argtypes = (c_void_p, c_void_p, c_ulong, c_long)

# ===========================================
# OPEN DEVICE
# ===========================================
m_dev = canDLL.ZCAN_OpenDevice(VCI_USBCAN2, 0, 0)
if m_dev == INVALID_DEVICE_HANDLE:
    print("Open Device failed!")
    exit(0)
print(f"Device opened: handle 0x{m_dev:x}")

# Configure baud rates for both channels
for ch in [0, 1]:
    canDLL.ZCAN_SetAbitBaud(m_dev, ch, 500000)
    canDLL.ZCAN_SetDbitBaud(m_dev, ch, 2000000)
    canDLL.ZCAN_SetCANFDStandard(m_dev, ch, 0)

# ===========================================
# INIT CAN CHANNELS
# ===========================================
init_config = ZCAN_CHANNEL_INIT_CONFIG()
init_config.can_type = TYPE_CANFD
init_config.config.canfd.mode = 0 if args.loopback == 0 else 1

dev_ch1 = canDLL.ZCAN_InitCAN(m_dev, 0, byref(init_config))
if dev_ch1 == INVALID_CHANNEL_HANDLE:
    print("Init CAN0 failed!")
    exit(0)
print("Init CAN0 OK!")

dev_ch2 = canDLL.ZCAN_InitCAN(m_dev, 1, byref(init_config))
if dev_ch2 == INVALID_CHANNEL_HANDLE:
    print("Init CAN1 failed!")
    exit(0)
print("Init CAN1 OK!")

# Start both channels
canDLL.ZCAN_StartCAN(dev_ch1)
canDLL.ZCAN_StartCAN(dev_ch2)
print("Both CAN channels started")

# ===========================================
# CONNECT TO KUKSA DATABROKER
# ===========================================
PADS_vss_signal = 'Vehicle.Cabin.Light.Spotlight.Row1.PassengerSide.IsLightOn'
print(f"Connecting to Kuksa databroker at {databroker_ip}:{databroker_port}...")

# ===========================================
# MAIN OPERATION
# ===========================================
try:
    with VSSClient(databroker_ip, databroker_port) as client:
        print("Connected to Kuksa Databroker")
        print("=== Sending CAN ID 0x58A test messages ===")

        # Create transmit frame
        frame = ZCAN_TransmitFD_Data()
        frame.transmit_type = 0
        frame.frame.eff = 0
        frame.frame.rtr = 0
        frame.frame.brs = 1
        frame.frame.can_id = 0x58A
        frame.frame.len = 8

        # ---- Send byte[0] = 0 ----
        for i in range(8):
            frame.frame.data[i] = 0
        frame.frame.data[0] = 0
        print("Sending ID 0x58A with byte[0] = 0")
        canDLL.ZCAN_TransmitFD(dev_ch1, byref(frame), 1)
        time.sleep(0.5)

        # ---- Send byte[0] = 2 ----
        for i in range(8):
            frame.frame.data[i] = 0
        frame.frame.data[0] = 2
        print("Sending ID 0x58A with byte[0] = 2")
        canDLL.ZCAN_TransmitFD(dev_ch1, byref(frame), 1)
        time.sleep(0.5)

        # Loopback receive (optional)
        if args.loopback == 1:
            print("Loopback enabled — waiting for received frames...")
            ret = canDLL.ZCAN_GetReceiveNum(dev_ch2, TYPE_CANFD)
            if ret > 0:
                rcv_msgs = (ZCAN_ReceiveFD_Data * ret)()
                num = canDLL.ZCAN_ReceiveFD(dev_ch2, byref(rcv_msgs), ret, 100)
                for i in range(num):
                    data = [rcv_msgs[i].frame.data[j] for j in range(rcv_msgs[i].frame.len)]
                    print(f"Loopback RX → ID: {hex(rcv_msgs[i].frame.can_id)}, Data: {data}")

        print("CAN ID 0x58A test complete")

except Exception as e:
    print(f"Error: {e}")
