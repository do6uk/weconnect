# Volkswagen We Connect with MQTT service
API for Python to interact with Volkswagen's service We Connect (formerly CarNet).
This fork based on the scripts of Trocotronic/weconnect and is enhanced with an MQTT service

## Information
This modules contains some of the methods to interact with Volkswagen's service We Connect. This API is made for Python and retrieves the information in JSON format. It can be imported into your application and interact with VW's servers directly.
This fork has a slightly modified `NativeAPI.py` and contains a script `weconnectMQTT.py` which can be used as service or in shell.
Edit `weconnectMQTT.py` to configure your car for MQTT and `credentials.py` to specify your username (e-mail), password and S-PIN.
After testing in shell you can install MQTT-bridge as service by modify and link `weconnectMQTT.service`.

## Features of MQTT-bridge
- connect to broker
- fetch data from WeConnect API
- pass some data to MQTT
- in SERVICE-mode listen MQTT to:
  - refresh data from API
  - control charger, climatisation, windowheater, honk and flash
  - control service itself
- in CLI-mode:
  - show data from API
  - control charger, climatisation, windowheater, honk and flash
  - Arguments:
    - `--version` show version
    - `--verbose` activate human-friendly output at shell *some arguments will set this by default*
    - `--info` set logging to *INFO*
    - `--debug` set logging to *DEBUG*
    - `--profile` showing some data from weconnect-profile
    - `--state` requesting short state for all cars *can be combined with vin, plate or name*
    - `--fullstate` requesting data for all cars *can be combined with vin, plate or name*
    - `--service` run as a service *will listen on MQTT-topics*
    - `--vin *VIN*` select car by vin (e.g. XXX...123) *for use with charger/clima/climatemp/window/honk/flash/state/fullstate*
    - `--plate *PLATE*` select car by plate (e.g. XXX-YY1234) *for use with charger/clima/climatemp/window/honk/flash/state/fullstate*
    - `--name *NAME*` select car by name (e.g. MyCar) *for use with charger/clima/climatemp/window/honk/flash/state/fullstate*
    - `--charger *CHARGER*` set charger to *1|0* or *on|off*
    - `--clima *CLIMA*` set climatisation to *1|0* or *on|off*
    - `--climatemp *CLIMATEMP*` set climatisation_temperature in centigrade to *XX.X*
    - `--window *WINDOW*` set windowheater to *1|0* or *on|off*
    - `--honk *HONK*` set honk to *1|0* or *on|off*
    - `--flash *FLASH*` set flash to *1|0* or *on|off*

## Install as service
1. Edit `credentials.py` to specify your username, password and S-PIN (WeConnect login)
2. Edit `weconnectMQTT.py` to define your car by *VIN*, link it to an MQTT *topic* and set friendly *name* and *plate* for use in CLI-mode. Set *hostname/ip*, *port* and a *basetopic* for your MQTT broker
3. Run `weconnectMQTT.py --fullstate --debug` and check if everything works
4. Modify *username* and *path* in `weconnectMQTT.service` and copy or link file to your *systemd/system* directory and enable it as daemon

## MQTT-topics to control cars and service
- /weconnectMQTT/set/service/ **0** or **off** request shutdown service. If you use it as daemon it will restart after that.
- /weconnectMQTT/get/state/ **1** request short state of all defined cars
- /weconnectMQTT/get/fullstate/ **1** request data of all defined cars
- /weconnectMQTT/car1/get/state/ **1** request short state for car with topic *car1*
- /weconnectMQTT/car1/get/charger/ **1** request charger state for car with topic *car1*
- /weconnectMQTT/car1/get/clima/ **1** request climatisation state for car with topic *car1*
- /weconnectMQTT/car1/get/position/ **1** request parkposition for car with topic *car1*
- /weconnectMQTT/car1/get/fullstate/ **1** request all data for car with topic *car1*
- /weconnectMQTT/car1/set/charger/ **0|1|on|off** set charger for car with topic *car1*
- /weconnectMQTT/car1/set/clima/ **0|1|on|off** set climatisation for car with topic *car1*
- /weconnectMQTT/car1/set/climatemp/ **XX.X** set climatisation_temperature in centigrade for car with topic *car1*
- /weconnectMQTT/car1/set/window/ **0|1|on|off** set windowheater for car with topic *car1*
- /weconnectMQTT/car1/set/flash/ **1|on** set flash for car with topic *car1*
- /weconnectMQTT/car1/set/honk/ **XX** ´set honk with *XX* seconds for car with topic *car1*
- /weconnectMQTT/active/ always publishing *1* while API is in use and sets *0* after finishing
- /weconnectMQTT/service/active/ publishing *1* in interval while service is running

## Features of API-framework
- Direct login with the same USER and PASSWORD you use.
- Session is stored to prevent massive logins.
- Auto-accept new Terms & Conditions.
- Available methods:
  - `get_personal_data()`
  - `get_real_car_data()`
  - `get_mbb_status()`
  - `get_identity_data()`
  - `get_vehicles()`
  - `get_vehicle_data(vin)`
  - `get_users(vin)`
  - `get_fences(vin)`
  - `get_fences_configuration()`
  - `get_speed_alerts(vin)`
  - `get_speed_alerts_configuration()`
  - `get_trip_data(vin, type='longTerm')`: `type` can be `'longTerm'`, `'shortTerm'` or `'cyclic'`.
  - `get_vsr(vin)`
  - `get_departure_timer(vin)`
  - `get_climater(vin)`
  - `get_position(vin)`
  - `get_destinations(vin)`
  - `get_charger(vin)`
  - `get_heating_status(vin)`
  - `get_history(vin)`
  - `get_roles_rights(vin)`
  - `get_fetched_role(vin)`
  - `get_vehicle_health_report(vin)`
  - `get_car_port_data(vin)`
  - `request_status_update(vin)`
  - `request_status(vin)`
  - `get_vsr_request(vin, reqId)`
  - `flash(vin, lat, long)`
  - `honk(vin, lat, long)`
  - `get_honk_and_flash_status(vin, rid)`
  - `get_honk_and_flash_configuration()`
  - `battery_charge(vin, action='off')`: `action` can be `'off'` or `'on'`.
  - `climatisation(vin, action='off')`: `action` can be `'off'` or `'on'`.
  - `climatisation_temperature(vin, temperature=21.5)`: `temperature` is a `float` in Celsius degrees.
  - `window_melt(vin, action='off')`: `action` can be `'off'` or `'on'`.
  - `heating(vin, action='off')`: `action` can be `'off'` or `'on'`.
  - `heating(vin, action='lock')`: `action` can be `'lock'` or `'unlock'`.
  - `parse_vsr(vsr)`
  - `set_logging_level(level)`: `level` can be `logging.DEBUG`, `logging.INFO`, `logging.WARN`, `logging.ERROR` or `logging.CRITICAL`.
  - `version()`

NOTE: `vin` is the Vehicle Identification Number, a string with capital letters and digits.
For Usage of API See `example.py`. 

## License
Under ODC Open Database License v1.0.
