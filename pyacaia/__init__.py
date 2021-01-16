#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2019 Luca Pinello
# Released under GPLv3
#This code is based on the javascript version available here https://github.com/bpowers/btscale
# Updated for the Pyxis scale by Dan Bodoh

__version__ = "0.4.0"

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
                if (d['name'] 
                    and (d['name'].startswith('ACAIA')
                        or d['name'].startswith('PYXIS')
                        or d['name'].startswith('PROCH'))):
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
                    if (desc=='Complete Local Name' 
                        and (value.startswith('ACAIA')
                             or value.startswith('PYXIS')
                             or value.startswith('PROCH'))):

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
    """Return a tuple - first element is the message, or None
       if one not yet found.  Second is are the remaining
       bytes, which can be empty
       Messages are encoded as the encode() function above,
       min message length is 6 bytes
       HEADER1 (0xef)
       HEADER1 (0xdd)
       command 
       length  (including this byte, excluding checksum)
       payload of length-1 bytes
       checksum byte1
       checksum byte2
       
    """
    messageStart = -1
   
    for i in range(len(bytes)-1):
        if bytes[i]==HEADER1 and bytes[i+1]==HEADER2:
            messageStart=i
            break
    if messageStart<0 or len(bytes)-messageStart<6:
        return (None,bytes)

    messageEnd  = messageStart+bytes[messageStart+3]+5

    if messageEnd>len(bytes):
        return (None,bytes)

    if messageStart>0:
        logging.debug("Ignoring "+str(i)+" bytes before header")

    cmd = bytes[messageStart+2]
    if (cmd !=12):
        logging.debug("Non event notification message command "+str(cmd))
        return (None,bytes[messageEnd:])

    msgType = bytes[messageStart+4]
    payloadIn = bytes[messageStart+5:messageEnd]

    return (Message(msgType,payloadIn),bytes[messageEnd:])


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


def encodeId(isPyxisStyle=False):
    if isPyxisStyle:
        payload = bytearray([0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x37,0x38,0x39,0x30,0x31,0x32,0x33,0x34])
    else:
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
            if self.interval==0:
                self.func()
            elif not self.timer or not self.timer.isAlive():
                self.timer=Timer(self.interval,self.func)
                self.timer.start()


class AcaiaScale(object):

    def __init__(self,mac,char_uuid=None,backend='bluepy',iface='hci0',weight_uuid=None):
        """For Pyxis-style devices, the UUIDs can be overridden.  char_uuid
           is the command UUID, and weight_uuid is where the notify comes
           from.  Old-style scales only specify char_uuid
        """

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
        self.weight_uuid=weight_uuid
        self.isPyxisStyle=(char_uuid and weight_uuid)
        self.char=None
        self.handle=None

        self.queue = None
        self.packet=None
        self.weight = None
        self.set_interval_thread=None
        self.last_heartbeat = 0


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

        while True:
            (msg,self.packet) = decode(self.packet)
            if not msg:
                return
            if msg.msgType==5:
                self.weight=msg.value
                logging.debug('weight: ' + str(msg.value)+' '+str(time.time()))
            else:
                logging.debug('non-weight response: '+str(msg.msgType))


    def connect(self):

        if self.connected:
            return

        self.queue= Queue(self.callback_queue)

        if self.backend=='bluepy':
            self.device=self.backend_class.Peripheral(self.mac, addrType=self.backend_class.ADDR_TYPE_PUBLIC)
            self.device=self.device.withDelegate(self)
            # MTU of 247 required by Pyxis for long notification payloads,
            # not sure if it is needed for older scales
            self.device.setMTU(247)
            foundCommandChar=False
            foundWeightChar=False
            pyxisWeightChar=None

            if self.char_uuid:
                self.char=self.device.getCharacteristics(uuid=self.char_uuid)[0]
                foundCommandChar=True
                self.isPyxisStyle=False
                if self.weight_uuid:
                    pyxisWeightChar=self.device.getCharacteristics(uuid=self.weight_uuid)[0]
                    self.isPyxisStyle=True
                logging.debug("Overriding characteristic UUIDs from constructor")
                foundWeightChar=True
            else:
                from bluepy.btle import UUID
                # Get all the characteristics to decide if we 
                # are connecting to an older scale or or a new Pyxis
                characteristics = self.device.getCharacteristics()
                pyxisWeightChar = None
                for char in characteristics:
                    if char.uuid==UUID('49535343-8841-43f4-a8d4-ecbe34729bb3'):
                        logging.debug("Has Pyxis-style command char")
                        self.char = char
                        self.char_uuid = str(self.char.uuid)
                        self.isPyxisStyle=True
                        foundCommandChar=True
                    elif char.uuid==UUID('49535343-1e4d-4bd9-ba61-23c647249616'):
                        logging.debug("Has Pyxis-style weight char")
                        pyxisWeightChar = char
                        self.weight_uuid = str(pyxisWeightChar.uuid)
                        foundWeightChar=True
                    elif char.uuid==UUID('00002a80-0000-1000-8000-00805f9b34fb'):
                        logging.debug("Has old-style char")
                        self.char = char
                        self.char_uuid = str(self.char.uuid)
                        # command and weight in the same characteristic
                        self.isPyxisStyle=False
                        foundCommandChar=True
                        foundWeightChar=True

            if not foundCommandChar:
                raise Exception("Could not find command characteristic")

            # Subscribe to notifications
            if self.isPyxisStyle:
                notifyDescriptors = pyxisWeightChar.getDescriptors(forUUID='2902',
                        hndEnd=pyxisWeightChar.valHandle+3)
                if notifyDescriptors:
                    self.device.writeCharacteristic(
                         notifyDescriptors[0].handle,
                         bytearray([0x01,0x00]),True)
                    foundWeightChar=True
            else:
                # Old-style scale: Hardcoded write to client config descriptor
                # which uses the same characteristic as the command
                # characteristic.  Instead of hardcoding,
                # this could probably be done like the Pyxis style
                self.device.writeCharacteristic(14,bytearray([0x01,0x00]))
                foundWeightChar=True

            if not foundWeightChar:
                raise Exception("Could not find weight characteristic");

        elif self.backend=='pygatt':
            # Only old-style supported with pygatt now
            if not self.char_uuid:
                self.char_uuid='00002a80-0000-1000-8000-00805f9b34fb'
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
        self.last_heartbeat = time.time()
        if self.backend=='bluepy':
            # For bluepy, use waitForNotifications() instead of Timer,
            # see notes in heartbeat()
            self.set_interval_thread=setInterval(self.heartbeat,0)
        elif self.backend=='pygatt':
            self.set_interval_thread=setInterval(self.heartbeat,5)
        self.set_interval_thread.start()

    def ident(self):

        if not self.connected:
            return False

        if self.backend=='bluepy':
            self.char.write(encodeId(self.isPyxisStyle), withResponse=False)
            self.char.write(encodeNotificationRequest(), withResponse=False)
        elif self.backend=='pygatt':
            self.device.char_write(self.char_uuid,encodeId(self.isPyxisStyle),wait_for_response=False)
            self.device.char_write(self.char_uuid,encodeNotificationRequest(),wait_for_response=False)

        return True

    def heartbeat(self):

        if not self.connected:
            return False

        try:
            if self.backend=='bluepy':
                # for bluepy, instead of waking up for a heartbeat, we 
                # do a waitForNotifications so that notifications from heartbeat
                # and notifications from waitForNotifications happen in the same
                # thread.  setInterval object calls heartbeat() without any 
                # timer delay
                self.device.waitForNotifications(1)
                if time.time() >= self.last_heartbeat+5:
                    # The official app sends a more complex heartbeat to Pyxis, once per
                    # second.  The Pyxis heartbeat has 3 messages:
                    # encodeId(True), encodeHeartbeat(), encode(6,[0]*16).
                    # But the Pyxis seems to work just fine with the single encodeHearbeat()
                    # once every 5 seconds as in the earlier scales.
                    self.last_heartbeat=time.time()
                    self.char.write(encodeHeartbeat(), withResponse=False)
                    logging.debug('Heartbeat success')
            elif self.backend=='pygatt':
                self.device.char_write_handle(self.handle,encodeHeartbeat(),wait_for_response=False)
                logging.debug('Heartbeat success')

            return True
        except Exception as e:
            logging.debug('Heartbeat failed '+str(e))


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
        self.set_interval_thread.join()



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

if __name__ == '__main__':
    main()
