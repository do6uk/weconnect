#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@name:		weconnectMQTT
@date:		2021-12-30
@author:	do6uk

Connecting to weconnect-service and request state of defined cars
Each car has own subtopic and selected state-vars will be published via MQTT
Script listens to individual MQTT-topics to refresh data or set honk, flash, climater or charger

Script based on the work of  Trocotronic/weconnect  on github
"""


## YOUR DATA

# Step 1: put your WeConnect-Logindata to credentials.py (read by NativeAPI.py)

# Step 2: define your cars here, you can temporarly switch an car inactive by setting 'active':False
# e.g.: mycars = [{'vin':'ABC12345','name':'WhatYouLike','topic':'myCar','plate':'WhatYouLike','active':True,'lat':0,'lon':0},{'vin':'ABC12345','name':'WhatYouLike2','topic':'myCar2','plate':'WhatYouLike2','active':False,'lat':0,'lon':0}]
mycars = [{'vin':'yourvin12345','name':'MyCar','topic':'car1','plate':'MY-C1234','active':True,'lat':0,'lon':0}]

# Step 3: configure your MQTT-broker
mqtt_broker = 'localhost'
mqtt_port = 1883
mqtt_base_topic = '/weconnectMQTT/'
mqtt_alive = 15		# interval in seconds to send alive-message via MQTT


## IMPORTS

from NativeAPI import WeConnect
import logging
import requests
import time,sys,random,json
import paho.mqtt.client as mqtt
import argparse
import signal
from datetime import datetime


## DEFAULTS & GLOBAL VARS

state_dict = {'0': 0, '1': 1,'off': 0,'on': 1,'connected': 1,'disconnected': 0,'locked': 1, 'unlocked': 0, 'heating': 1, 'false': 0, 'true': 1, 'False': 0, 'True': 1, False: 0, True: 1}
state_string = {'0': 'off', '1': 'on', 0: 'off', 1: 'on', 'on': 'on', 'off': 'off'}

lastrun = 0
verbose = False
log_stream = False
mqtt_bridge = True
log_level = logging.ERROR 	#default level
cli_log_level = logging.WARN	#level in CLI-Mode
service_log_level = logging.WARN	#level in SERVICE-Mode

version = '20211230.1'

## ARGUMENT

parser = argparse.ArgumentParser(description='weconnectMQTT verbindet die VW WeConnect API mit einem MQTT-Broker und bietet ein kleines Shell-Interface')
parser.add_argument('--version', action='store_true',help='zeigt dies Versionsinfo')
parser.add_argument('--verbose', action='store_true',help='Ausgabe der Daten in lesbarer Form')
parser.add_argument('--info', action='store_true',help='Ausgabe von Meldungen aus dem internen Logger')
parser.add_argument('--debug', action='store_true',help='Ausgabe aller Meldungen aus dem internen Logger')
parser.add_argument('--profile', action='store_true',help='Anzeige WeConnect-Profildaten')
parser.add_argument('--state', action='store_true',help='Abruf kurzer Status *kann mit vin/plate/name kombiniert werden')
parser.add_argument('--fullstate', action='store_true',help='Abruf langer Status *kann mit vin/plate/name kombiniert werden')
parser.add_argument('--service', action='store_true',help='aktivieren der MQTT-Bridge als Service')
parser.add_argument('--vin', default=False,help='Auswahl des Fahrzeugs per FIN (XXX...123) *für charger/clima/climatemp/window/honk/flash/state/fullstate')
parser.add_argument('--plate', default=False,help='Auswahl des Fahrzeugs per Kennzeichen (XXX-YY1234) *für charger/clima/climatemp/window/honk/flash/state/fullstate')
parser.add_argument('--name', default=False,help='Auswahl des Fahrzeugs per Name (ABC) *für charger/clima/climatemp/window/honk/flash/state/fullstate')
parser.add_argument('--charger',help='schalte Ladung (1|0 oder on|off)')
parser.add_argument('--clima',help='schalte Klimatisierung (1|0 oder on|off)')
parser.add_argument('--climatemp',help='setze Solltemperatur in Grad-C (XX.X)')
parser.add_argument('--window',help='schalte Scheibenheizung (1|0 oder on|off)')
parser.add_argument('--honk',help='aktiviere Hupe (1|0 oder on|off)')
parser.add_argument('--flash',help='aktiviere Blinker (1|0 oder on|off)')
args = vars(parser.parse_args())

if args['verbose'] or args['debug'] or args['version']:
	print('\nweconnectMQTT Version {}\n'.format(version))
	if args['version']:
		sys.exit()

if args['profile'] or args['fullstate'] or args['state'] or args['verbose']:
	verbose = True
	log_stream = True
	log_level = cli_log_level

if args['service']:
	log_stream = True
	log_level = service_log_level

if args['info']:
	log_stream = True
	log_level = logging.INFO

if args['debug']:
	log_stream = True
	log_level = logging.DEBUG

logger = logging.getLogger('weconnectMQTT')
logger.setLevel(log_level)
logger.propagate = False

logformat = logging.Formatter('%(asctime)s %(levelname)s\t%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_log = logging.StreamHandler()
console_log.setFormatter(logformat)
console_log.setLevel(log_level)
logger.addHandler(console_log)

logger.debug('weconnectMQTT {} pre-initialized'.format(version))

## FUNCTIONS

def car_by(item, value):
	global mycars
	for car in mycars:
		if car[item] == value:
			return car
		else:
			return False

def car_savepos(vin, lat, lon):
	global mycars
	for car in mycars:
		if car['vin'] == vin:
			car['lat'] = lat
			car['lon'] = lon
			return True
	return False

def car_getpos(vin):
	global mycars
	for car in mycars:
		if car['vin'] == vin:
			return (car['lat'],car['lon'])
	return False

def handler_stop_signals(signum, frame):
	global mqtt_bridge
	logger.warn('MQTT Service stopped - canceled by signal {}!'.format(signal.Signals(signum).name))
	mqtt_bridge = False

def state_conv(msg):
	try:
		return state_dict[msg]
	except:
		return msg

def on_message(client, userdata, message):
	global mqtt_bridge,mycars

	topic = message.topic
	payload = str(message.payload.decode("utf-8"))
	logger.debug('MQTT MSG HANDLE Topic: {} Payload: {}'.format(topic,payload))

	if mconnect:
		mclient.publish(mqtt_base_topic+'active',1)

	for car in mycars:
		if not car['active']: continue
		if topic == mqtt_base_topic+car['topic']+'/set/flash':
			logger.info('MQTT SET Flash > {}'.format(payload))
			if verbose:
				print('\nSET Blinker',payload)
			mclient.publish(mqtt_base_topic+car['topic']+'/response/flash',do_flash(car['vin']))

		if topic == mqtt_base_topic+car['topic']+'/set/honk':
			logger.info('MQTT SET Honk > {}'.format(payload))
			if verbose:
				print('\nSET Hupe',payload)
			mclient.publish(mqtt_base_topic+car['topic']+'/response/honk',do_honk(car['vin'],int(payload)))

		if topic == mqtt_base_topic+car['topic']+'/set/clima':
			logger.info('MQTT SET Clima > {}'.format(payload))
			if verbose:
				print('\nSET Klimatisierung',payload)
			mclient.publish(mqtt_base_topic+car['topic']+'/response/clima',switch_clima(car['vin'],payload))

		if topic == mqtt_base_topic+car['topic']+'/set/climatemp':
			logger.info('MQTT SET Climatemp > {}'.format(payload))
			if verbose:
				print('\nSET Klimatisierung Soll-Temp.',payload)
			mclient.publish(mqtt_base_topic+car['topic']+'/response/climatemp',set_climatemp(car['vin'],payload))

		if topic == mqtt_base_topic+car['topic']+'/set/window':
			logger.info('MQTT SET Windowheater > {}'.format(payload))
			if verbose:
				print('\nSET Scheibenheizung',payload)
			mclient.publish(mqtt_base_topic+car['topic']+'/response/window',switch_window(car['vin'],payload))

		if topic == mqtt_base_topic+car['topic']+'/set/charger':
			logger.info('MQTT SET Charger > {}'.format(payload))
			if verbose:
				print('\nSET Sofortladen',payload)
			mclient.publish(mqtt_base_topic+car['topic']+'/response/charger',switch_charger(car['vin'],payload))

		if topic == mqtt_base_topic+car['topic']+'/get/charger':
			if verbose:
				print('\nGET Ladesystem',payload)
			result = get_charger(car['vin'])
			logger.info('MQTT GET Charger > {}'.format(result))

		if topic == mqtt_base_topic+car['topic']+'/get/position':
			if verbose:
				print('\nGET Position')
			result = get_position(car['vin'])
			logger.info('MQTT GET Position > {}'.format(result))

		if topic == mqtt_base_topic+car['topic']+'/get/clima':
			if verbose:
				print('\nGET Klimatisierung')
			result = get_clima(car['vin'])
			logger.info('MQTT GET Clima > {}'.format(result))

		if topic == mqtt_base_topic+car['topic']+'/get/state':
			if verbose:
				print('\nGET kurzer Status',payload)
			result = get_carstate(car['vin'])
			logger.info('MQTT GET Shortstate > {}'.format(result))

		if topic == mqtt_base_topic+car['topic']+'/get/fullstate':
			if verbose:
				print('\nGET langer Status',payload)
			result = get_fullstate(car['vin'])
			logger.info('MQTT GET Fullstate > {}'.format(result))

	if topic == mqtt_base_topic+'get/state':
		if verbose:
			print('\nGET kurzer Status für alle Fahrzeuge',payload)
		result = get_state()
		logger.info('MQTT GET Shortstate > {}'.format(result))

	if topic == mqtt_base_topic+'get/fullstate':
		if verbose:
			print('\nGET langer Status für alle Fahrzeuge',payload)
		result = get_fullstate()
		logger.info('MQTT GET Fullstate > {}'.format(result))

	if topic == mqtt_base_topic+'set/service':
		logger.info('MQTT SET Service > {}'.format(payload))
		if verbose:
			print('\nSET MQTT Service',payload)
		mqtt_bridge = bool(state_conv(payload))
		if not mqtt_brigde:
			logger.warn('MQTT Service stopping - requested from MQTT!')
		mclient.publish(mqtt_base_topic+'service/response',True)

	if mconnect:
		ts = datetime.now().strftime('%d.%m.%y %H:%M:%S')
		logger.debug('MQTT MSG HANDLE finished!')
		mclient.publish(mqtt_base_topic+'active/time',ts)
		mclient.publish(mqtt_base_topic+'active',0)

def on_disconnect(client, userdata, rc):
	logger.warn('MQTT disconnected ({}) - try reconnect ...'.format(rc))
	if rc != 0:
		re_connect(client)

def re_connect(client):
	global mqtt_broker, mqtt_port, mqtt_base_topic, mconnect, mqtt_bridge
	try:
		logger.debug('MQTT re-connecting ... {}:{}'.format(mqtt_broker,mqtt_port))
		client.connect(mqtt_broker, mqtt_port)
		mconnect = 1
		client.publish(mqtt_base_topic+'active',1)
		for car in cars:
			if not car['active']: continue
			client.subscribe([(mqtt_base_topic+car['topic']+'/set/#',0),(mqtt_base_topic+car['topic']+'/get/#',0)])
		logger.info('MQTT connected {}:{}'.format(mqtt_broker,mqtt_port))
	except:
		logger.error('MQTT disconnected - reconnect failed!')
		mconnect = 0
		mqtt_bridge = 0
		sys.exit(1)

def switch_clima(vin,state):
	car = car_by('vin',vin)
	try:
		vwc = WeConnect()
		result = vwc.login()
	except:
		logger.warn('VWC SET Clima failed - Gateway offline {}'.format(result))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/clima','offline',1)
		result = False

	newstate = state_string[state]
	try:
		r = vwc.climatisation(vin, action=newstate)
		logger.debug('VWC SET Clima {} > {}'.format(newstate,r['action']['actionState']))
		if r['action']['actionState'] == 'queued':
			result = True
	except:
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/clima','error',1)
		result = False

	if verbose:
		print('\nSende Klimatisierung > {} result {}'.format(newstate,result))
	
	logger.info('VWC SET Clima - Result {}'.format(result))
	return result

def switch_charger(vin,state):
	car = car_by('vin',vin)
	try:
		vwc = WeConnect()
		result = vwc.login()
	except:
		logger.warn('VWC SET Charger failed - Gateway offline {}'.format(result))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/charger','offline',1)
		result = False

	newstate = state_string[state]
	try:
		r = vwc.battery_charge(vin, action=newstate)
		logger.debug('VWC SET Charger {} > {}'.format(newstate,r['action']['actionState']))
		if r['action']['actionState'] == 'queued':
			result =  True
	except:
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/charger','error',1)
		result = False

	if verbose:
		print('\nSende Sofortladen > {} result {}'.format(newstate,result))

	logger.info('VWC SET Charger - Result {}'.format(result))
	return result

def set_climatemp(vin,temp):
	car = car_by('vin',vin)
	try:
		vwc = WeConnect()
		result = vwc.login()
	except:
		logger.warn('VWC SET Charger failed - Gateway offline {}'.format(result))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/clima/temp','offline',1)
		result = False

	temp = float(temp)
	if temp >= 16 and temp <=28:
		newtemp = round(0.5 * round(float(temp)/0.5),1)
		try:
			r = vwc.climatisation_temperature(vin, temperature=int(newtemp))
			logger.debug('VWC SET Climatemp {} > {}'.format(newtemp,r['action']['actionState']))
			if r['action']['actionState'] == 'queued':
				result =  True
		except:
			if mconnect:
				mclient.publish(mqtt_base_topic+car['topic']+'/clima/temp','error',1)
			result = False
	else:
		logger.warn('VWC SET Climatemp failed - Temp out of range {}'.format(newtemp))
		result = False

	if verbose:
		print('\nSende Klima-Temperatur > {} result {}'.format(newstate,result))

	logger.info('VWC SET Climatemp - Result {}'.format(result))
	return result


def do_flash(vin,duration=1):
	car = car_by('vin',vin)
	try:
		vwc = WeConnect()
		result = vwc.login()
	except:
		logger.warn('VWC SET Flash failed - Gateway offline {}'.format(result))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/flash','offline',1)
		result = False

	try:
		r = vwc.flash(vin, car['lat'], car['lon'])
		logger.debug('VWC SET Flash > {}'.format(r['action']['actionState']))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/flash','ok',1)
		result = True
	except:
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/flash','error',1)
		result = False

	if verbose:
		print('\nSende Blinker > {} result {}'.format(newstate,result))

	logger.info('VWC SET Flash - Result {}'.format(result))
	return result

def do_honk(vin,duration=1):
	car = car_by('vin',vin)

	try:
		vwc = WeConnect()
		result = vwc.login()
	except:
		logger.warn('VWC SET Honk failed - Gateway offline {}'.format(result))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/honk','offline',1)
		result = False

	try:
		r = vwc.honk(vin, car['lat'], car['lon'], duration)
		logger.debug('VWC SET Honk {} > {}'.format(duration,r['action']['actionState']))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/honk','ok',1)
		result = True
	except:
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/honk','error',1)
		result = False

	if verbose:
		print('\nSende Hupe > {} result {}'.format(newstate,result))

	logger.info('VWC SET Honk - Result {}'.format(result))
	return result

def switch_window(vin,state):
	car = car_by('vin',vin)
	try:
		vwc = WeConnect()
		result = vwc.login()
	except:
		logger.warn('VWC SET Windowheater failed - Gateway offline {}'.format(result))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/clima/windowheat','offline',1)
		result = False

	newstate = state_string[state]
	try:
		r = vwc.window_melt(vin, action=newstate)
		logger.debug('VWC SET Windowheater {} > {}'.format(newstate,r['action']['actionState']))
		if r['action']['actionState'] == 'queued':
			result = True
	except:
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/clima/windowheat','error',1)
		result = False

	if verbose:
		print('\nSende Scheibenheizung > {} result {}'.format(newstate,result))

	logger.info('VWC SET Windowheater - Result {}'.format(result))
	return result

def get_clima(vin):
	car = car_by('vin',vin)
	try:
		vwc = WeConnect()
		result = vwc.login()
	except:
		logger.warn('VWC GET Clima failed - Gateway offline {}'.format(result))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/clima','offline',1)
		result = False

	try:
		if verbose:
			print('\nKlimatisierungsdaten abrufen ...')

		clima = vwc.get_climater(vin)
		temp_target = round(clima['climater']['settings']['targetTemperature']['content']/10-273,1)
		temp_outside = round(clima['climater']['status']['temperatureStatusData']['outdoorTemperature']['content']/10-273,1)
		clima_state = clima['climater']['status']['climatisationStatusData']['climatisationState']['content']
		clima_state_ts = clima['climater']['status']['climatisationStatusData']['climatisationState']['timestamp']
		windowheat_state = clima['climater']['status']['windowHeatingStatusData']['windowHeatingStateRear']['content']
		windowheat_state_ts = clima['climater']['status']['windowHeatingStatusData']['windowHeatingStateRear']['timestamp']
		logger.debug('CLIMATER state: {} @ {}'.format(clima_state,clima_state_ts))
		logger.debug('CLIMATER temp_target: {}, temp_outside: {} @ {}'.format(temp_target,temp_outside,clima_state_ts))
		logger.debug('CLIMATER windowheater: {} @ {}'.format(windowheat_state,windowheat_state_ts))
		#logger.debug('CLIMATER state {}, windowheater {}, temp_target {}, temp_outside {} @ time {}'.format(clima_state,windowheat_state,temp_target,temp_outside,clima_state_ts))

		try:
			parking = clima['climater']['status']['vehicleParkingClockStatusData']['vehicleParkingClock']['content']
		except:
			parking = 'unbekannt'

		if verbose:
			print('Klimatisierung',clima_state,'Solltemp',temp_target)
			print('Scheibenheizung',windowheat_state,'Außentemperatur',temp_outside)
			print('geparkt',parking)

		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/clima/temp/outside',temp_outside)
			mclient.publish(mqtt_base_topic+car['topic']+'/clima/temp/target',temp_target)
			mclient.publish(mqtt_base_topic+car['topic']+'/clima/state',clima_state)
			mclient.publish(mqtt_base_topic+car['topic']+'/clima/state/time',clima_state_ts)
			mclient.publish(mqtt_base_topic+car['topic']+'/clima/windowheat',windowheat_state)
			mclient.publish(mqtt_base_topic+car['topic']+'/clima/windowheat/time',windowheat_state_ts)
			mclient.publish(mqtt_base_topic+car['topic']+'/clima/parktime',parking)
		result = True
	except:
		try:
			strdata = json.dumps(clima)
		except:
			strdata = 'empty'
		logger.error('VWC GET Climastate failed - data not readable {}'.format(strdata))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/clima','error',1)
		result = False

	if verbose:
		print('\nAbruf Klimatisierungsdaten > result {}'.format(result))

	logger.info('VWC GET Climastate - Result {}'.format(result))
	return result


def get_charger(vin):
	car = car_by('vin',vin)
	try:
		vwc = WeConnect()
		result = vwc.login()
	except:
		logger.warn('VWC GET Charger failed - Gateway offline {}'.format(result))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/charger','offline',1)
		result = False

	try:
		if verbose:
			print('\nLadedaten abrufen ...')

		charger = vwc.get_charger(vin)
		# lademodus: off, conditioning,
		charging_mode = charger['charger']['status']['chargingStatusData']['chargingMode']['content']
		charging_mode_ts = charger['charger']['status']['chargingStatusData']['chargingMode']['timestamp']
		charging_state = charger['charger']['status']['chargingStatusData']['chargingState']['content']
		charging_state_ts = charger['charger']['status']['chargingStatusData']['chargingState']['timestamp']
		charging_time = charger['charger']['status']['batteryStatusData']['remainingChargingTime']['content']
		charging_time_ts = charger['charger']['status']['batteryStatusData']['remainingChargingTime']['timestamp']
		logger.debug('CHARGER mode: {} @ {}'.format(charging_mode,charging_mode_ts))
		logger.debug('CHARGER state: {} @ {}'.format(charging_state,charging_state_ts))
		logger.debug('CHARGER remain: {} @ {}'.format(charging_time,charging_time_ts))
		#logger.debug('CHARGER mode: {}, state: {}, remain: {} @ {}'.format(charging_mode,charging_state,charging_time,charging_time_ts))

		driverange = charger['charger']['status']['cruisingRangeStatusData']['primaryEngineRange']['content']
		driverange_ts = charger['charger']['status']['cruisingRangeStatusData']['primaryEngineRange']['timestamp']
		level = charger['charger']['status']['batteryStatusData']['stateOfCharge']['content']
		level_ts = charger['charger']['status']['batteryStatusData']['stateOfCharge']['timestamp']
		logger.debug('CHARGER SoC: {} @ {}'.format(level,level_ts))
		logger.debug('CHARGER driverange: {} @ {}'.format(driverange,driverange_ts))
		#logger.debug('CHARGER SoC: {}, driverange: {} @ {}'.format(level,driverange,level_ts))

		plug = charger['charger']['status']['plugStatusData']['plugState']['content']
		plug_ts = charger['charger']['status']['plugStatusData']['plugState']['timestamp']
		pluglock = charger['charger']['status']['plugStatusData']['lockState']['content']
		pluglock_ts = charger['charger']['status']['plugStatusData']['lockState']['timestamp']
		logger.debug('CHARGER plug: {} @ {}'.format(plug,plug_ts))
		logger.debug('CHARGER pluglock: {} @ {}'.format(pluglock,pluglock_ts))
		#logger.debug('CHARGER plug: {}, pluglock: {} @ {}'.format(plug,pluglock,pluglock_ts))

		if verbose:
			print('Lademodus',charging_mode,'@',charging_mode_ts)
			print('Ladestecker',plug,'@',level_ts,pluglock,'@',pluglock_ts)
			print('Laden',charging_state,'@',charging_state_ts)
			print('Reichweite',driverange,'@',driverange_ts)
			print('Batterie',level,'@',level_ts)
			print('Restladedauer',charging_time,'@',charging_time_ts)

		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/charger/active',state_conv(charging_state))
			mclient.publish(mqtt_base_topic+car['topic']+'/charger/active/time',charging_state_ts)
			mclient.publish(mqtt_base_topic+car['topic']+'/charger/mode',charging_mode)
			mclient.publish(mqtt_base_topic+car['topic']+'/charger/range',driverange)
			mclient.publish(mqtt_base_topic+car['topic']+'/charger/level',level)
			mclient.publish(mqtt_base_topic+car['topic']+'/charger/estimated',charging_time)
			mclient.publish(mqtt_base_topic+car['topic']+'/charger/plug',state_conv(plug))
			mclient.publish(mqtt_base_topic+car['topic']+'/charger/plug/time',plug_ts)
			mclient.publish(mqtt_base_topic+car['topic']+'/charger/pluglock',state_conv(pluglock))
			mclient.publish(mqtt_base_topic+car['topic']+'/charger/pluglock/time',pluglock_ts)
		result = True
	except:
		try:
			strdata = json.dumps(charger)
		except:
			strdata = 'empty'
		logger.error('VWC GET Charger failed - data not readable {}'.format(strdata))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/charger','error',1)
		result = False

	if verbose:
		print('\nAbruf Klimatisierungsdaten > result {}'.format(result))

	logger.info('VWC GET Climastate - Result {}'.format(result))
	return result


def get_position(vin):
	global pos_lat,pos_lon
	car = car_by('vin',vin)

	try:
		vwc = WeConnect()
		result = vwc.login()
	except:
		logger.warn('VWC GET Position failed - Gateway offline {}'.format(result))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/position','offline',1)
		result = False

	try:
		if verbose:
			print('\nPositionsdaten abrufen ...')

		posdata = vwc.get_position(vin)
		pos_time = posdata['storedPositionResponse']['parkingTimeUTC']
		pos_head = posdata['storedPositionResponse']['position']['heading']['direction']
		pos_lat = posdata['storedPositionResponse']['position']['carCoordinate']['latitude']
		pos_lon = posdata['storedPositionResponse']['position']['carCoordinate']['longitude']
		
		car_savepos(vin,pos_lat,pos_lon)
		lat = pos_lat/1e6
		lon = pos_lon/1e6
		logger.debug('POSITION latlon: {}, {} heading: {} @ {}'.format(lat,lon,pos_head,pos_time))

		try:
			data = requests.get('https://nominatim.openstreetmap.org/search.php?q='+str(lat)+','+str(lon)+'&polygon_geojson=1&format=jsonv2')
			j = data.json()
			if (len(j) > 0):
				pos_name = j[0]['display_name']
				logger.debug('POSITION nominatim: {}'.format(pos_name))
		except:
			logger.warn('OSM Nominatim failed - address not readable {}'.format(json.dumps(data)))
			pos_name = 'unbekannt'

		if verbose:
			print('Position',str(lat)+', '+str(lon),'Richtung',pos_head,'\n ',pos_name)

		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/position/latitude',pos_lat)
			mclient.publish(mqtt_base_topic+car['topic']+'/position/longitude',pos_lon)
			mclient.publish(mqtt_base_topic+car['topic']+'/position/latlon',str(lat)+','+str(lon))
			mclient.publish(mqtt_base_topic+car['topic']+'/position/heading',pos_head)
			mclient.publish(mqtt_base_topic+car['topic']+'/position/address',pos_name)
			mclient.publish(mqtt_base_topic+car['topic']+'/position/time',pos_time)
			mclient.publish(mqtt_base_topic+car['topic']+'/position','ok')
		
		result = True
	except:
		try:
			strdata = json.dumps(posdata)
		except:
			strdata = 'empty'
		logger.error('VWC GET Position failed - data not readable {}'.format(strdata))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/position','error',1)
		result = False

	if verbose:
		print('\nAbruf Positionsdaten > result {}'.format(result))

	logger.info('VWC GET Position - Result {}'.format(result))
	return result


def get_carstate(vin):
	car = car_by('vin',vin)

	try:
		vwc = WeConnect()
		result = vwc.login()
	except:
		logger.warn('VWC GET State failed - Gateway offline {}'.format(result))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/connect','offline',1)
		result = False

	try:
		vehicle = vwc.get_vehicle_data(vin)
		isConnect = state_conv(vehicle['vehicleDataDetail']['isConnect'])
	except:
		isConnect = 0
	
	mclient.publish(mqtt_base_topic+car['topic']+'/connect',isConnect,1)
	logger.debug('STATE VIN {} connected {}'.format(vin,isConnect))

	try:
		if verbose:
			print('\nFahrzeugstatus abrufen ...')
	
		vsr = vwc.get_vsr(vin)
		vsrdata = vwc.parse_vsr(vsr)

		doorlock = vsrdata['doors']['lock_left_front']
		logger.debug('STATE door {}'.format(doorlock))
		driverange = vsrdata['status']['primary_range']
		logger.debug('STATE driverange {}'.format(driverange))
		level = vsrdata['status']['state_of_charge']
		logger.debug('STATE SoC {}'.format(level))
		temp_outside = vsrdata['status']['temperature_outside']
		logger.debug('STATE temp_outside {}'.format(temp_outside))

		if verbose:
			print('Fahrertür',doorlock,'Ladestand',level,'Reichweite',driverange,'Temp',temp_outside)

		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/door/lock',doorlock,1)
			driverange = driverange.replace(' km','')
			mclient.publish(mqtt_base_topic+car['topic']+'/charger/range',driverange,1)
			level = level.replace(' %','')
			mclient.publish(mqtt_base_topic+car['topic']+'/charger/level',level,1)
			temp_outside = temp_outside.replace(' dK','')
			temp = round(int(temp_outside)/10-273,1)
			mclient.publish(mqtt_base_topic+car['topic']+'/clima/temp/outside',temp,1)

		result = True
	except:
		try:
			strdata = json.dumps(vsrdata)
		except:
			strdata = 'empty'
		logger.error('VWC GET State failed - vsr-data not readable {}'.format(strdata))
		if mconnect:
			mclient.publish(mqtt_base_topic+car['topic']+'/connect','error',1)
		result = False

	if verbose:
		print('\nAbruf Fahrzeugstatus > result {}'.format(result))

	logger.info('VWC GET State - Result {}'.format(result))
	return result

def get_state(vin=False):
	car = car_by('vin',vin)
	if car:
		cars = [car]
	else:
		cars = mycars

	result = True
	activecar = False
	for car in cars:
		if not car['active']: continue
		activecar = True
		if not get_carstate(car['vin']):
			result = False

	if not activecar:
		logger.warn('GET State - no active car in mycars')
		if verbose:
			print('\nFEHLER: kein aktives Fahrzeug in mycars')
	elif not result:
		logger.warn('GET State - least one car failed')
		if verbose:
			print('\nFEHLER: mindestens ein Fahrzeug konnte nicht abgerufen werden')
	else:
		logger.debug('GET State - all cars successfull')
	return result

def get_fullstate(vin=False):
	car = car_by('vin',vin)
	if car:
		cars = [car]
	else:
		cars = mycars
	
	result = True
	activecar = False
	for car in cars:
		if not car['active']: continue
		activecar = True
		logger.debug('GET Fullstate by calling all subroutines for {} ...'.format(car['name']))
		
		if get_carstate(car['vin']) and get_clima(car['vin']) and get_position(car['vin']) and get_charger(car['vin']):
			pass
			#result = True
		else:
			logger.warn('GET Fullstate - least one subroutine failed')
			result = False
	
	if not activecar:
		logger.warn('GET Fullstate - no active car in mycars')
		if verbose:
			print('\nFEHLER: kein aktives Fahrzeug in mycars')
	elif not result:
		logger.warn('GET Fullstate - least one car failed')
		if verbose:
			print('\nFEHLER: mindestens ein Fahrzeug konnte nicht abgerufen werden')
	else:
		logger.debug('GET Fullstate - all cars successfull')
	return result

## MQTT

client_id = f'python-mqtt-{random.randint(0, 1000)}'
logger.debug('MQTT connecting ... {}:{}'.format(mqtt_broker,mqtt_port))
try:
	if verbose:
		print('Verbinde mit MQTT',mqtt_broker,mqtt_port)
	mclient = mqtt.Client(client_id)
	mclient.on_message = on_message
	mclient.on_disconnect = on_disconnect
	mclient.connect(mqtt_broker, mqtt_port)
	mconnect = 1
	mclient.publish(mqtt_base_topic+'active',1)
	logger.info('MQTT connected @ {}:{}'.format(mqtt_broker,mqtt_port))
except:
	logger.error('MQTT connetion failed!')
	mconnect = 0


## WeConnect-Verbindung

try:
	result = False
	vwc = WeConnect()
	result = vwc.login()
	logger.debug('VWC checking Gateway > login {}'.format(result))
except:
	logger.error('VWC checking Gateway > failed - Gateway seems offline {}'.format(result))
	sys.exit(1)


## MAIN

if args['service']:
	logger.debug('SERVICE initialize ...')
	if verbose:
		print('\nMQTT Service ...')

	logger.debug('SERVICE register signalhandle ...')
	signal.signal(signal.SIGTERM, handler_stop_signals)
	
	if not mconnect:
		logger.error('MQTT disconnected - MQTT Service failed!')
		sys.exit(1)

	logger.debug('SERVICE register MQTT client  ...')
	mclient.loop_start()
	mclient.publish(mqtt_base_topic+'service/active',1)
	logger.debug('SERVICE subscribe MQTT topics  ...')
	
	mqtt_subscribed = False
	for car in mycars:
		if not car['active']: continue
		logger.debug('SERVICE subscribe {} for {}  ...'.format(mqtt_base_topic+car['topic'],car['name']))
		mclient.subscribe([(mqtt_base_topic+car['topic']+'/set/#',0),(mqtt_base_topic+car['topic']+'/get/#',0)])
		mqtt_subscribed = True
	
	if mqtt_subscribed:
		get_fullstate()
	else:
		logger.warn('SERVICE not car-topics subscribed - no active car in mycars')
		if verbose:
			print('\nWARNUNG: keine aktiven Fahrzeuge in mycars!')

	mclient.publish(mqtt_base_topic+'active/time',datetime.now().strftime('%d.%m.%y %H:%M:%S'))
	mclient.publish(mqtt_base_topic+'active',0)
	mqtt_bridge = True
	try:
		while mqtt_bridge:
			if time.time()-lastrun > mqtt_alive:
				logger.debug('SERVICE is alive')
				mclient.publish(mqtt_base_topic+'service/active',1)
				mclient.publish(mqtt_base_topic+'service/active/time',datetime.now().strftime('%H:%M:%S'))
				lastrun = time.time()
			time.sleep(1)

	except KeyboardInterrupt:
		logger.warn('SERVICE stopped - canceled by user!')

	if verbose:
		print('\nMQTT Service beendet!')

	mclient.publish(mqtt_base_topic+'service/active',0)
	mclient.publish(mqtt_base_topic+'service/active/offline',datetime.now().strftime('%H:%M:%S'))
	time.sleep(2)
	logger.debug('SERVICE clean exit')
	sys.exit()
	
if args['vin'] or args['plate'] or args['name']:
	if args['vin']:
		car = car_by('vin',args['vin'])
		logger.debug('CLI search car in mycars by vin {} > {}'.format(args['vin'],bool(car)))
		if car and verbose:
			print('Fahrzeug über VIN gefunden',car['name'])
	elif args['plate']:
		car = car_by('plate',args['plate'])
		logger.debug('CLI search car in mycars by plate {} > {}'.format(args['plate'],bool(car)))
		if car and verbose:
			print('Fahrzeug über Kennzeichen gefunden',car['name'])
	elif args['name']:
		car = car_by('name',args['name'])
		logger.debug('CLI search car in mycars by name {} > {}'.format(args['name'],bool(car)))
		if car and verbose:
			print('Fahrzeug über Name gefunden',car['name'])
	if not car:
		logger.error('CLI car not found in mycars {} {} {}'.format(args['vin'],args['plate'],args['name']))
		if verbose:
			print('FEHLER: Fahrzeug nicht gefunden')
		sys.exit(1)
else:
	car = False
	if len(mycars) == 1:
		if mycars[0]['active']:
			car = mycars[0]
			logger.debug('only one car in mycars > selected {}'.format(car['name']))
		else:
			logger.warn('CLI only car in mycars not active - may cause problems')
	elif not args['service'] and not args['state'] and not args['fullstate']:
		logger.warn('CLI no car selected - may cause problems')

logger.debug('CLI parsing arguments ...')

if args['profile']:
	try:
		cars = vwc.get_real_car_data()
		profile = vwc.get_personal_data()
		mbb = vwc.get_mbb_status()

		print('\nWeConnect-Profil')
		print('Hallo {}!'.format(profile['nickname']))
		print(' {}\n {} {}'.format(profile['salutation'], profile['firstName'], profile['lastName']))
		print(' Profil vollständig?', mbb['profileCompleted'])
		print(' S-PIN aktiviert?', mbb['spinDefined'])
		print(' CarNet Länderkennung:',mbb['carnetEnrollmentCountry'])
		if (cars and len(cars)):
			print('bekannte Fahrzeuge')
			for car in cars['realCars']:
				vin = car['vehicleIdentificationNumber']
				print('\tFIN:', vin,'\tKurzname:', car['nickname'])
			get_carstate(vin)
	except:
		logger.error('VWC GET Profile failed - data not readable {}'.format(json.dumps(profile)))
		if verbose:
			print('FEHLER: WeConnect Profil konnte nicht abgerufen werden')

if args['state']:
	if verbose:
		print('\nkurzer Fahrzeugzustand ...')
	if car:
		get_state(car['vin'])
	else:
		get_state()

if args['fullstate']:
	if verbose:
		print('\nFahrzeugzustand ...')
	if car:
		get_fullstate(car['vin'])
	else:
		get_fullstate()

if args['charger'] != None and car:
	newstate = state_conv(args['charger'])
	logger.info('CLI SET charger {} > {}'.format(newstate,car['name']))
	if verbose:
		print('\nLadung schalten ...',newstate)
	switch_charger(car['vin'],newstate)
elif args['charger'] != None:
	logger.error('CLI SET charger failed - no car selected {}'.format(args['charger']))
	if verbose:
		print('\nFEHLER: Ladung schalten - kein Fahrzeug gewählt')
	sys.exit(1)

if args['clima'] != None and car:
	newstate = state_conv(args['clima'])
	logger.info('CLI SET clima {} > {}'.format(newstate,car['name']))
	if verbose:
		print('\nKlimatisierung schalten ...',newstate)
	switch_clima(car['vin'],newstate)
elif args['clima'] != None:
	logger.error('CLI SET clima failed - no car selected {}'.format(args['clima']))
	if verbose:
		print('\nFEHLER: Klimatisierung schalten - kein Fahrzeug gewählt')
	sys.exit(1)

if args['climatemp'] != None and car:
	newtemp = state_conv(args['climatemp'])
	logger.info('CLI SET climatemp {} > {}'.format(newtemp,car['name']))
	if verbose:
		print('\nKlimatisierungs Temp setzen ...',newtemp)
	set_climatemp(car['vin'],newtemp)
elif args['climatemp'] != None:
	logger.error('CLI SET climatemp failed - no car selected {}'.format(args['climatemp']))
	if verbose:
		print('\nFEHLER: Klimatisierung Temp setzen - kein Fahrzeug gewählt')
	sys.exit(1)

if args['window'] != None and car:
	newstate = state_conv(args['window'])
	logger.info('CLI SET windowheater {} > {}'.format(newstate,car['name']))
	if verbose:
		print('\nScheibenheizung schalten ...',newstate)
	switch_window(car['vin'],newstate)
elif args['window'] != None:
	logger.error('CLI SET windowheater failed - no car selected {}'.format(args['window']))
	if verbose:
		print('\nFEHLER: Scheibenheizung schalten - kein Fahrzeug gewählt')
	sys.exit(1)

if args['honk'] != None and car:
	newstate = state_conv(args['honk'])
	logger.info('CLI SET honk {} > {}'.format(newstate,car['name']))
	if verbose:
		print('\nHupe aktivieren ...',newstate)
	get_position(car['vin'])
	do_honk(car['vin'],newstate)
elif args['honk'] != None:
	logger.error('CLI SET honk failed - no car selected {}'.format(args['honk']))
	if verbose:
		print('\nFEHLER: Hupe aktivieren - kein Fahrzeug gewählt')
	sys.exit(1)

if args['flash'] != None and car:
	newstate = state_conv(args['flash'])
	logger.info('CLI SET flash {} > {}'.format(newstate,car['name']))
	if verbose:
		print('\nBlinker aktivieren ...',newstate)
	get_position(car['vin'])
	do_flash(car['vin'],newstate)
elif args['flash'] != None:
	logger.error('CLI SET honk failed - no car selected {}'.format(args['flash']))
	if verbose:
		print('\nFEHLER: Blinker aktivieren - kein Fahrzeug gewählt')
	sys.exit(1)

if len(sys.argv) == 1:
	parser.print_help(sys.stderr)

if mconnect:
	mclient.publish(mqtt_base_topic+'active/time',datetime.now().strftime('%d.%m.%y %H:%M:%S'))
	mclient.publish(mqtt_base_topic+'active',0)

logger.debug('CLI clean exit')
sys.exit()