# pyacaia

Python module to interact with Acaia scales (https://acaia.co/collections/coffee-scales) via Bluetooth (BLE). 

This code was inspired by the javascript version available here https://github.com/bpowers/btscale

## 0. Requirements
Linux, Python (>=2.7 or >=3.5) and  bluepy (https://github.com/lucapinello/bluepy)
(pygatt >=4.0.3 is also partially supported https://github.com/peplin/pygatt;
 Pyxis not supported under pygatt)

This package has been tested on a RasperryPI ZeroW with Raspbian GNU/Linux 9 (stretch) and on Ubuntu Linux 20.04, and with the Lunar and Pyxis scales.

## 1. Install with:

`pip install pyacaia`

## 2. Short example
```
    from pyacaia import AcaiaScale
    
    scale=AcaiaScale(mac='00:1C:97:17:FD:97')
    
    scale.auto_connect() #to pick the first available
    
    # Or if you know the address use:
    # scale.connect()
    
    # battery value in percent
    print(scale.battery)

    # scale units is 'grams' or 'ounces'
    print(scale.units)

    # minutes of idle before auto-off
    print(scale.auto_off)

    # will the scale beep when a button is pressed?
    if scale.beep_on:
	print('It beeps!')
    else:
	print('It is silent!')

    # is the timer running?
    if scale.timer_running:
	print('timer is running')
	# elapsed time is in seconds, if timer is paused
	# the value will be the displayed time
	# Due to bluetooth transit time, the value
	# may be slightly different than displayed
        print('elapsed time:',scale.get_elapsed_time())

    # Tare the scale
    scale.tare()

    # Control the timer
    scale.startTimer()
    time.sleep(2)
    scale.stopTimer()
    scale.resetTimer()

    #read and print the weight every 0.5 sec for 5 sec 
    for i in range(10):
        print scale.weight # this is the property we can use to read the weigth in realtime
        time.sleep(0.5)
	# check if the scale is still connected, perhaps it was turned off?
	if not scale.connected:
	    break

    scale.disconnect()

``` 

Pyacaia now calls bluepy's Peripheral.waitForNotifications() internally.  If your application uses waitForNotications() directly with 0.3.0 or earlier, that call should be removed.

By default the backend used is bluepy, but also pygatt is supported. In that case use:

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

