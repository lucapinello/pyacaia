# pyacaia

Python module to interact with Acaia scales (https://acaia.co/collections/coffee-scales) via Bluetooth (BLE). 

This code was inspired by the javascript version available here https://github.com/bpowers/btscale

## 0. Requirements
Linux, Python (2.7) and pygatt (https://github.com/peplin/pygatt)

## 1. Install with:

`pip install pyacaia`

## 2. Short example
```

    scale=AcaiaScale()
    
    scale.auto_connect() #to pick the first available
    
    # Or if you know the address use:
    # scale.connect('00:1C:97:17:FD:97')
    
    #read and print the weight every 0.5 sec for 5 sec 
    for i in range(10):
        print scale.weight # this is the property we can use to read the weigth in realtime
        time.sleep(0.5)

    scale.disconnect()

```    
   
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

