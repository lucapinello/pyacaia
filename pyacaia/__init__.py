#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2019 Luca Pinello
# Released under GPLv3
#This code is based on the javascript version available here https://github.com/bpowers/btscale

__version__ = "0.1.0"

import logging
import time
from threading import Thread, Timer
from pygatt import GATTToolBackend


root = logging.getLogger()
root.setLevel(logging.INFO)

#logging.basicConfig()
logging.getLogger('pygatt').setLevel(logging.WARNING)

HEADER1 = 0xef
HEADER2 = 0xdd

def find_acaia_devices(timeout=3):
    print('Looking for ACAIA devices...')
    adapter = GATTToolBackend('hci0')
    adapter.reset()
    adapter.start(False)
    devices=adapter.scan(timeout=timeout,run_as_root=True)
    addresses=[]
    for d in devices:
        if d['name'] and d['name'].startswith('ACAIA'):
            print (d['name'],d['address'])
            addresses.append(d['address'])
    adapter.stop()
    return addresses

def print_acaia_characteristics(device_address):
    adapter = GATTToolBackend('hci0')
    adapter.reset()
    adapter.start(False)
    device = adapter.connect(device_address)

    try:
        string_type = unicode
    except NameError:
        string_type = str

    for chars in device.discover_characteristics().values():
        print(chars.uuid,device.get_handle(string_type(chars.uuid)))
    adapter.stop()

class Queue(object):

    def __init__(self,callback):
        self.queue=[]
        self.callback=callback
        self.running=False

    def add(self,data):

        self.queue.append(data)

        if not self.running:
            self.dequeue()

    def dequeue(self):

        self.running=True

        val=self.queue.pop(0)
        while (val):
            self.callback(val)

            if self.queue:
                val=self.queue.pop(0)
            else:
                val=None

        self.running=False


    def next(self):
        return dequeue(self)


class Message(object):

    def __init__(self,msgType,payload):
        self.msgType=msgType
        self.payload=payload
        self.value=None

        if (self.msgType ==5):
            value= ((payload[1] & 0xff) << 8) + (payload[0] & 0xff)
            unit=  payload[4] & 0xFF;

            if (unit == 1): value /= 10.0
            elif (unit == 2): value /= 100.0
            elif (unit == 3): value /= 1000.0
            elif (unit == 4): value /= 10000.0
            else: raise Exception('unit value not in range %d:' % unit)

            if ((payload[5] & 0x02) == 0x02):
                value *= -1

            self.value=value


def encode(msgType,payload):
    bytes=bytearray(5+len(payload))

    bytes[0] = HEADER1
    bytes[1] = HEADER2
    bytes[2] = msgType
    cksum1 = 0
    cksum2 = 0


    for i in range(len(payload)):
        val = payload[i] & 0xff
        bytes[3+i] = val
        if (i % 2 == 0):
            cksum1 += val
        else:
            cksum2 += val

    bytes[len(payload) + 3] = (cksum1 & 0xFF)
    bytes[len(payload) + 4] = (cksum2 & 0xFF)

    return bytes


def decode(bytes):
    if (bytes[0] != HEADER1 and bytes[1] != HEADER2):
        return

    cmd = bytes[2]

    if (cmd !=12):
        logging.debug("Non event notification message:%s" %bytes)
        return

    msgType = bytes[4]
    payloadIn=bytes[5:]

    return Message(msgType,payloadIn)


def encodeEventData(payload):
    bytes= bytearray(len(payload)+1)
    bytes[0] = len(payload) + 1

    for i in range(len(payload)):
        bytes[i+1]=payload[i] & 0xff

    return encode(12,bytes)


def encodeNotificationRequest():
    payload=[
    	0,  # weight
    	1,  # weight argument
    	1,  # battery
    	2,  # battery argument
    	2,  # timer
    	5,  # timer argument
    	3,  # key
    	4   # setting
    ]
    return encodeEventData(payload)


def encodeId():
    payload = bytearray([0x2d,0x2d,0x2d,0x2d,0x2d,0x2d,0x2d,0x2d,0x2d,0x2d,0x2d,0x2d,0x2d,0x2d,0x2d])
    return encode(11,payload)


def encodeHeartbeat():
    payload = [2,0]
    return encode(0, payload)


def encodeTare():
    payload = [0];
    return encode(4, payload)

class setInterval(Thread):

    def __init__(self,func,interval):

        Thread.__init__(self)
        self.keep_going=False
        self.func=func
        self.interval=interval
        self.timer=None

    def stop(self):
        self.keep_going=False

    def run(self):

        self.keep_going=True

        while self.keep_going:

            if not self.timer or not self.timer.isAlive():
                self.timer=Timer(self.interval,self.func)
                self.timer.start()


class AcaiaScale(object):

    def __init__(self,
                 characteristic_uuid="00002a80-0000-1000-8000-00805f9b34fb",
                 gatt_backend='hci0'):

        self.connected = False

        self.adapter=None
        self.device_address=None
        self.device = None

        self.characteristic_uuid=characteristic_uuid
        self.gatt_backend=gatt_backend

        self.queue = None
        self.packet=None
        self.weight = None
        self.set_interval_thread=None


    def addBuffer(self,buffer2):

        packet_len=0

        if self.packet:
            packet_len=len(self.packet)

        result= bytearray(packet_len+len(buffer2))

        for i in range(packet_len):
            result[i]=self.packet[i]

        for i in range(len(buffer2)):
            result[i+packet_len]=buffer2[i]

        self.packet=result


    def characteristicValueChanged(self,handle,value):
        #print handle,value
        self.queue.add(value)


    def callback_queue(self,payload):
        #print('This is the queue')
        self.addBuffer(payload)
        if len(self.packet)<=3:
            return

        msg = decode(self.packet)
        self.packet=None

        if not msg:
            logging.debug('characteristic value update, but no message')
            return

        if msg.msgType==5:
            self.weight=msg.value
            logging.debug('weight: ' + str(msg.value))
        else:
            logging.debug('non-weight response')
            logging.debug(msg.value)
            pass

    def auto_connect(self):
        if self.connected:
            return
        logging.info('Trying to find an ACAIA scale...')
        addresses=find_acaia_devices()

        #This will connect to the first discovered
        if addresses:
            device_address=addresses[0]
            logging.info('Connecting to:%s' % device_address)
            self.connect(device_address)
        else:
            logging.info('No ACAIA scale found')


    def connect(self,device_address):

        if self.connected:
            return

        self.device_address=device_address

        self.queue= Queue(self.callback_queue)

        self.adapter = GATTToolBackend(self.gatt_backend)
        self.adapter.reset()
        self.adapter.start(False)
        self.device = self.adapter.connect(self.device_address)

        #self.device.receive_notification(13,bytearray([0x01, 0x00]))
        self.device.subscribe(self.characteristic_uuid, self.characteristicValueChanged)
        self.notificationsReady()

    def disconnect(self):
        self.connected=False
        self.device.disconnect()
        self.adapter.stop()
        self.set_interval_thread.stop()

    def notificationsReady(self):
        logging.info('Scale Ready!')
        self.connected = True;
        self.ident();
        self.set_interval_thread=setInterval(self.heartbeat,5)
        self.set_interval_thread.start()

    def ident(self):
        if not self.connected:
            return False
        self.device.char_write(self.characteristic_uuid,encodeId(),wait_for_response=False)
        self.device.char_write(self.characteristic_uuid,encodeNotificationRequest(),wait_for_response=False)
        return True

    def heartbeat(self):
        if not self.connected:
            return False

        try:
            self.device.char_write(self.characteristic_uuid,encodeHeartbeat(),wait_for_response=False)
            logging.debug('Heartbeat success')
            return True
        except:
            logging.debug('Heartbeat failed')


    def tare(self):
        if not self.connected:
            return False
        self.device.char_write(self.characteristic_uuid,encodeTare(),wait_for_response=False)

        return True


def main():

    addresses=find_acaia_devices()

    time.sleep(1)
    if addresses:
        print_acaia_characteristics(addresses[0])
    else:
        print('No Acaia devices found')
    
    time.sleep(1)
    scale=AcaiaScale()

    #scale.connect('00:1C:97:17:FD:97')
    scale.auto_connect() #to pick the first available

    for i in range(10):
        print(scale.weight)
        time.sleep(0.5)

    scale.disconnect()
    time.sleep(5)
	
if __name__ == '__main__':
    main()
