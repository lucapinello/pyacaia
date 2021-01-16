# pyacaia

Python module to interact with Acaia scales (https://acaia.co/collections/coffee-scales) via Bluetooth (BLE). 

This code was inspired by the javascript version available here https://github.com/bpowers/btscale

## 0. Requirements
Linux, Python (>=2.7 or >=3.5) and  bluepy (https://github.com/lucapinello/bluepy)
(pygatt >=4.0.3 is also partially supported https://github.com/peplin/pygatt;
 Pyxis not supported under pygatt)

This package has been tested on a RasperryPI ZeroW with Raspbian GNU/Linux 9 (stretch)

## 1. Install with:

`pip install pyacaia`

## 2. Short example
```
    from pyacaia import AcaiaScale
    
    scale=AcaiaScale(mac='00:1C:97:17:FD:97')
    
    scale.auto_connect() #to pick the first available
    
    # Or if you know the address use:
    # scale.connect()
    
    #read and print the weight every 0.5 sec for 5 sec 
    for i in range(10):
        print scale.weight # this is the property we can use to read the weigth in realtime
        time.sleep(0.5)

    scale.disconnect()

``` 

API change:

Pyacaia now calls bluepy's Peripheral.waitForNotifications() internally.  If your application uses waitForNotications() directly, it should be removed.

By default the backend used is blupy, but also pygatt is supported. In that case use:

   scale=AcaiaScale(mac='00:1C:97:17:FD:97',backend='pygatt')
   
## 3. Other functions that may be helpful
Find and list all the acaia scales that are on and in range

`addresses=find_acaia_devices()`

Print BLE charachteristic of the first available acaia in the list of addresses

```
if addresses:
        print_acaia_characteristics(addresses[0])
    else:
        print 'No Acaia devices found'
```

