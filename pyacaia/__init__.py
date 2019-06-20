#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2019 Luca Pinello
# Released under GPLv3
#This code is based on the javascript version available here https://github.com/bpowers/btscale

__version__ = "0.2.0"

import logging
import time
from threading import Thread, Timer

root = logging.getLogger()
root.setLevel(logging.INFO)

logging.getLogger('pygatt').setLevel(logging.WARNING)

HEADER1 = 0xef
HEADER2 = 0xdd

def find_acaia_devices(timeout=3,backend='bluepy'):

    addresses=[]
    print('Looking for ACAIA devices...')

    if backend=='pygatt':
        try:
            from pygatt import GATTToolBackend
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
        except:
            raise Exception('pygatt is not installed')


    elif backend=='bluepy':

        try:
            from bluepy.btle import Scanner, DefaultDelegate

            class ScanDelegate(DefaultDelegate):
                def __init__(self):
                    DefaultDelegate.__init__(self)

            scanner = Scanner().withDelegate(ScanDelegate())
            devices = scanner.scan(timeout)

            addresses=[]
            for dev in devices:
                for (adtype, desc, value) in dev.getScanData():
                    if desc=='Complete Local Name' and value.startswith('ACAIA'):
                        print(value, dev.addr)
                        addresses.append(dev.addr)

        except:
            raise Exception('bluepy is not installed')

    return addresses

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

    def __init__(self,mac,char_uuid="00002a80-0000-1000-8000-00805f9b34fb",backend='bluepy',iface='hci0'):

        if backend=='pygatt':
            try:
                from pygatt import GATTToolBackend
            except:
                raise Exception('pygatt is not installed')
            self.backend_class=GATTToolBackend

        elif backend=='bluepy':
            try:
                from bluepy import btle
            except:
                raise Exception('bluepy is not installed')
            self.backend_class=btle

        else:
            raise Exception('Backend not supported')

        self.backend=backend
        self.iface=iface
        self.mac=mac
        self.adapter=None
        self.device = None
        self.connected = False

        self.char_uuid=char_uuid
        self.char=None
        self.handle=None

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

    def handleDiscovery(self, scanEntry, isNewDev, isNewData):
        pass #DBG("Discovered device", scanEntry.addr)

    def handleNotification(self,handle,value):
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


    def connect(self):

        if self.connected:
            return

        self.queue= Queue(self.callback_queue)

        if self.backend=='bluepy':
            self.device=self.backend_class.Peripheral(self.mac, addrType=self.backend_class.ADDR_TYPE_PUBLIC)
            self.device=self.device.withDelegate(self)
            self.char=self.device.getCharacteristics(uuid=self.char_uuid)[0]
            self.device.writeCharacteristic(14,bytearray([0x01,0x00]))

        elif self.backend=='pygatt':
            self.adapter = self.backend_class(self.iface)
            self.adapter.reset()
            self.adapter.start(False)
            self.device = self.adapter.connect(self.mac)
            self.device.subscribe(self.char_uuid, self.characteristicValueChanged)
            self.handle=self.device.get_handle(self.char_uuid)

        time.sleep(0.5)
        self.notificationsReady()

    def auto_connect(self):
        if self.connected:
            return
        logging.info('Trying to find an ACAIA scale...')
        addresses=find_acaia_devices()

        #This will connect to the first discovered
        if addresses:
            device_address=addresses[0]
            logging.info('Connecting to:%s' % device_address)
            self.connect()
        else:
            logging.info('No ACAIA scale found')

    def notificationsReady(self):
        logging.info('Scale Ready!')
        self.connected = True
        self.ident()
        self.set_interval_thread=setInterval(self.heartbeat,5)
        self.set_interval_thread.start()

    def ident(self):

        if not self.connected:
            return False

        if self.backend=='bluepy':
            self.char.write(encodeId(), withResponse=False)
            self.char.write(encodeNotificationRequest(), withResponse=False)
        elif self.backend=='pygatt':
            self.device.char_write(self.char_uuid,encodeId(),wait_for_response=False)
            self.device.char_write(self.char_uuid,encodeNotificationRequest(),wait_for_response=False)

        return True

    def heartbeat(self):

        if not self.connected:
            return False

        try:
            if self.backend=='bluepy':
                self.char.write(encodeHeartbeat(), withResponse=False)
            elif self.backend=='pygatt':
                self.device.char_write_handle(self.handle,encodeHeartbeat(),wait_for_response=False)

            logging.debug('Heartbeat success')
            return True
        except:
            logging.debug('Heartbeat failed')


    def tare(self):
        if not self.connected:
            return False
        if self.backend=='bluepy':
            self.char.write( encodeTare(), withResponse=False)
        elif self.backend=='pygatt':
            self.device.char_write(self.char_uuid,encodeTare(),wait_for_response=False)

        return True


    def disconnect(self):

        self.connected=False
        if self.device:

            if self.backend=='pygatt':

                self.device.disconnect()
                self.adapter.stop()

            elif self.backend=='bluepy':
                self.device.disconnect()
        self.set_interval_thread.stop()



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
