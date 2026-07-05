#!/usr/bin/env/python
# File name   : server.py
# Production  : GWR
# Website     : www.adeept.com
# Author      : William
# Date        : 2020/03/17

import time
import threading
import move
import Adafruit_PCA9685
import os
import info
import RPIservo

import functions
import robotLight
import switch
import socket

#websocket
import asyncio
import websockets

import json
import app

OLED_connection = 0
'''
try:
	import OLED
	screen = OLED.OLED_ctrl()
	screen.start()
	screen.screen_show(1, 'ADEEPT.COM')
except:
	OLED_connection = 0
	print('OLED disconnected')
	pass
'''

functionMode = 0
speed_set = 100
rad = 0.5
turnWiggle = 60

scGear = RPIservo.ServoCtrl()
P_sc = RPIservo.ServoCtrl()
T_sc = RPIservo.ServoCtrl()


# modeSelect = 'none'
modeSelect = 'PT'

init_pwm0 = 300
init_pwm1 = 300
init_pwm2 = 300
init_pwm3 = scGear.initPos[3]
init_pwm4 = scGear.initPos[4]

# Channel -> the controller that physically drives it. Channels 0, 1, 2 are the
# only servos: 0 = camera tilt (T_sc), 1 = camera pan (P_sc), 2 = steering (scGear).
SERVO_CONTROLLERS = {0: T_sc, 1: P_sc, 2: scGear}


def apply_servo_calibration(cal, move=False):
	"""Push the saved calibration (from app.py) into the live servo controllers.

	Sets each servo's centre (initPos) and travel limits (min/max) so the camera
	'Center' button and steering rest where the user calibrated them. All three
	controller arrays are kept consistent for the shared channels. When move=True
	the servo is eased to its new centre so the effect is visible while
	calibrating; at start-up we set the values silently and let the normal init
	move settle them.
	"""
	global init_pwm0, init_pwm1, init_pwm2
	servos = cal.get('servos', {}) if isinstance(cal, dict) else {}
	if not isinstance(servos, dict):
		servos = {}
	for ch, primary in SERVO_CONTROLLERS.items():
		raw = servos.get(str(ch))
		if not isinstance(raw, dict):
			continue
		try:
			center = int(raw['center'])
			mn = int(raw['min'])
			mx = int(raw['max'])
		except (KeyError, TypeError, ValueError):
			continue
		for ctrl in (scGear, P_sc, T_sc):
			ctrl.minPos[ch] = mn
			ctrl.maxPos[ch] = mx
			ctrl.initPos[ch] = center
		if ch == 0:
			init_pwm0 = center
		elif ch == 1:
			init_pwm1 = center
		elif ch == 2:
			init_pwm2 = center
		if move:
			try:
				primary.setPWM(ch, center)
			except Exception:
				pass


# Load calibration before the first init move so the robot settles on the
# calibrated centres rather than the hard-coded 300.
try:
	apply_servo_calibration(app.get_current_servo_calibration(), move=False)
except Exception as e:
	print('Servo calibration not applied at start-up:', e)

scGear.moveInit()
P_sc.start()
T_sc.start()

# Flask runs in this same process, so a save from the web UI can be applied to
# the running servos immediately (no restart).
try:
	app.register_servo_apply(lambda cal: apply_servo_calibration(cal, move=True))
except Exception as e:
	print('Servo calibration live-apply hook not registered:', e)

fuc = functions.Functions()
fuc.start()

curpath = os.path.realpath(__file__)
thisPath = "/" + os.path.dirname(curpath)

direction_command = 'no'
turn_command = 'no'

def servoPosInit():
	scGear.initConfig(2,init_pwm2,1)
	P_sc.initConfig(1,init_pwm1,1)
	T_sc.initConfig(0,init_pwm0,1)


def replace_num(initial,new_num):   #Call this function to replace data in '.txt' file
	global r
	newline=""
	str_num=str(new_num)
	with open(thisPath+"/RPIservo.py","r") as f:
		for line in f.readlines():
			if(line.find(initial) == 0):
				line = initial+"%s" %(str_num+"\n")
			newline += line
	with open(thisPath+"/RPIservo.py","w") as f:
		f.writelines(newline)


def FPV_thread():
	global fpv
	fpv=FPV.FPV()
	fpv.capture_thread(addr[0])


def ap_thread():
	os.system("sudo create_ap wlan0 eth0 Adeept_Robot 12345678")


def functionSelect(command_input, response):
	global functionMode
	if 'scan' == command_input:
		if OLED_connection:
			screen.screen_show(5,'SCANNING')
		if modeSelect == 'PT':
			radar_send = fuc.radarScan()
			print(radar_send)
			response['title'] = 'scanResult'
			response['data'] = radar_send
			time.sleep(0.3)

	elif 'findColor' == command_input:
		if OLED_connection:
			screen.screen_show(5,'FindColor')
		if modeSelect == 'PT':
			flask_app.modeselect('findColor')

	elif 'motionGet' == command_input:
		if OLED_connection:
			screen.screen_show(5,'MotionGet')
		flask_app.modeselect('watchDog')

	elif 'stopCV' == command_input:
		flask_app.modeselect('none')
		switch.switch(1,0)
		switch.switch(2,0)
		switch.switch(3,0)
		move.motorStop()

	elif 'KD' == command_input:
		if OLED_connection:
			screen.screen_show(5,'POLICE')
		servoPosInit()
		fuc.keepDistance()
		RL.police()
	
	elif 'automaticOff' == command_input:
		RL.pause()
		fuc.pause()
		move.motorStop()
		time.sleep(0.3)
		move.motorStop()

	elif 'automatic' == command_input:
		if OLED_connection:
			screen.screen_show(5,'Automatic')
		if modeSelect == 'PT':
			fuc.automatic()
		else:
			fuc.pause()

	elif 'automaticOff' == command_input:
		fuc.pause()
		move.motorStop()
		time.sleep(0.2)
		move.motorStop()

	elif 'trackLine' == command_input:
		servoPosInit()
		fuc.trackLine()
		if OLED_connection:
			screen.screen_show(5,'TrackLine')

	elif 'trackLineOff' == command_input:
		fuc.pause()
		move.motorStop()

	elif 'steadyCamera' == command_input:
		if OLED_connection:
			screen.screen_show(5,'SteadyCamera')
		fuc.steady(T_sc.lastPos[2])

	elif 'steadyCameraOff' == command_input:
		fuc.pause()
		move.motorStop()

	elif 'speech' == command_input:
		RL.both_off()
		fuc.speech()

	elif 'speechOff' == command_input:
		RL.both_off()
		fuc.pause()
		move.motorStop()
		time.sleep(0.3)
		move.motorStop()


def switchCtrl(command_input, response):
	if 'Switch_1_on' in command_input:
		switch.switch(1,1)

	elif 'Switch_1_off' in command_input:
		switch.switch(1,0)

	elif 'Switch_2_on' in command_input:
		switch.switch(2,1)

	elif 'Switch_2_off' in command_input:
		switch.switch(2,0)

	elif 'Switch_3_on' in command_input:
		switch.switch(3,1)

	elif 'Switch_3_off' in command_input:
		switch.switch(3,0) 


# WebSocket keepalive. The browser automatically answers ping frames even when
# page-level JavaScript timers are delayed during a long touch hold, so connection
# liveness should be handled here instead of by timing out application messages.
WS_PING_INTERVAL = 2.0
WS_PING_TIMEOUT = 4.0
WS_CLOSE_TIMEOUT = 1.0


def emergency_stop():
	"""Immediately halt all motion. Safe to call from any state."""
	global direction_command, turn_command
	direction_command = 'no'
	turn_command = 'no'
	try:
		move.motorStop()
	except Exception:
		pass
	try:
		scGear.moveAngle(2, 0)          # re-centre steering
	except Exception:
		pass
	try:
		fuc.pause()                     # halt any autonomous function
	except Exception:
		pass
	try:
		flask_app.modeselect('none')    # stop CV-driven motion
	except Exception:
		pass
	try:
		RL.both_off()
	except Exception:
		pass


def leds_inverted():
	"""Whether the 'Invert direction lights' UI setting is on."""
	try:
		return bool(app.get_current_settings().get('invertLEDs'))
	except Exception:
		return False


def drive_leds(raw_dir):
	"""Light the direction LEDs for a raw motor command.

	forward -> white headlights, backward -> red. When 'Invert direction lights'
	is on the two are swapped, so the lights match the button you pressed even
	while 'Invert forward / reverse' is remapping the motors.
	"""
	forward = (raw_dir == 'forward')
	if leds_inverted():
		forward = not forward
	try:
		if forward:
			RL.both_on()
		else:
			RL.red()
	except Exception:
		pass


def turn_signals_inverted():
	"""Whether the 'Invert turn signals' UI setting is on."""
	try:
		return bool(app.get_current_settings().get('invertTurnSignals'))
	except Exception:
		return False


def turn_leds(raw_turn):
	"""Light the turn-signal LEDs for a raw steer command (left/right).

	Swapped when 'Invert turn signals' is on so the indicator matches the button
	you pressed even while 'Invert steering' is remapping the steering servo.
	"""
	left = (raw_turn == 'left')
	if turn_signals_inverted():
		left = not left
	try:
		if left:
			RL.turnLeft()
		else:
			RL.turnRight()
	except Exception:
		pass


def robotCtrl(command_input, response):
	global direction_command, turn_command
	if 'E_STOP' == command_input:
		emergency_stop()

	elif 'forward' == command_input:
		direction_command = 'forward'
		move.motor_left(1, 0, speed_set)
		move.motor_right(1, 0, speed_set)
		drive_leds('forward')

	elif 'backward' == command_input:
		direction_command = 'backward'
		move.motor_left(1, 1, speed_set)
		move.motor_right(1, 1, speed_set)
		drive_leds('backward')

	elif 'DS' in command_input:
		direction_command = 'no'
		move.motorStop()
		if turn_command == 'left':
			RL.both_off()
			turn_leds('left')
		elif turn_command == 'right':
			RL.both_off()
			turn_leds('right')
		elif turn_command == 'no':
			RL.both_off()


	elif 'left' == command_input:
		turn_command = 'left'
		scGear.moveAngle(2, 30)
		RL.both_off()
		turn_leds('left')

	elif 'right' == command_input:
		turn_command = 'right'
		scGear.moveAngle(2,-30)
		RL.both_off()
		turn_leds('right')

	elif 'TS' in command_input:
		turn_command = 'no'
		scGear.moveAngle(2, 0)
		if direction_command == 'forward':
			drive_leds('forward')
		elif direction_command == 'backward':
			RL.both_off()
			drive_leds('backward')
		elif direction_command == 'no':
			RL.both_off()


	elif 'lookleft' == command_input:
		P_sc.singleServo(1, 1, 7)

	elif 'lookright' == command_input:
		P_sc.singleServo(1,-1, 7)

	elif 'LRstop' in command_input:
		P_sc.stopWiggle()


	elif 'up' == command_input:
		T_sc.singleServo(0, 1, 7)

	elif 'down' == command_input:
		T_sc.singleServo(0,-1, 7)

	elif 'UDstop' in command_input:
		T_sc.stopWiggle()


	elif 'home' == command_input:
		# Camera "Center" button: recentre the camera servos only, on their
		# calibrated centres (initPos). moveServoInit takes channel IDs, so pass
		# the channels, not the PWM values. Steering (CH2) is deliberately left
		# alone here; it recentres on steer-release (TS) and on E_STOP.
		T_sc.moveServoInit([0])      # camera tilt
		P_sc.moveServoInit([1])      # camera pan


def configPWM(command_input, response):
	global init_pwm0, init_pwm1, init_pwm2, init_pwm3, init_pwm4

	if 'SiLeft' in command_input:
		numServo = int(command_input[7:])
		if numServo == 0:
			init_pwm0 -= 1
			T_sc.setPWM(0,init_pwm0)
		elif numServo == 1:
			init_pwm1 -= 1
			P_sc.setPWM(1,init_pwm1)
		elif numServo == 2:
			init_pwm2 -= 1
			scGear.setPWM(2,init_pwm2)

	if 'SiRight' in command_input:
		numServo = int(command_input[8:])
		if numServo == 0:
			init_pwm0 += 1
			T_sc.setPWM(0,init_pwm0)
		elif numServo == 1:
			init_pwm1 += 1
			P_sc.setPWM(1,init_pwm1)
		elif numServo == 2:
			init_pwm2 += 1
			scGear.setPWM(2,init_pwm2)

	if 'PWMMS' in command_input:
		numServo = int(command_input[6:])
		if numServo == 0:
			T_sc.initConfig(0, init_pwm0, 1)
			replace_num('init_pwm0 = ', init_pwm0)
		elif numServo == 1:
			P_sc.initConfig(1, init_pwm1, 1)
			replace_num('init_pwm1 = ', init_pwm1)
		elif numServo == 2:
			scGear.initConfig(2, init_pwm2, 2)
			replace_num('init_pwm2 = ', init_pwm2)


	if 'PWMINIT' == command_input:
		print(init_pwm1)
		servoPosInit()

	elif 'PWMD' == command_input:
		init_pwm0,init_pwm1,init_pwm2,init_pwm3,init_pwm4=300,300,300,300,300
		T_sc.initConfig(0,300,1)
		replace_num('init_pwm0 = ', 300)

		P_sc.initConfig(1,300,1)
		replace_num('init_pwm1 = ', 300)

		scGear.initConfig(2,300,1)
		replace_num('init_pwm2 = ', 300)


def update_code():
	# Update local to be consistent with remote
	projectPath = thisPath[:-7]
	with open(f'{projectPath}/config.json', 'r') as f1:
		config = json.load(f1)
		if not config['production']:
			print('Update code')
			# Force overwriting local code
			if os.system(f'cd {projectPath} && sudo git fetch --all && sudo git reset --hard origin/master && sudo git pull') == 0:
				print('Update successfully')
				print('Restarting...')
				os.system('sudo reboot')
			
def wifi_check():
	try:
		s =socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
		s.connect(("1.1.1.1",80))
		ipaddr_check=s.getsockname()[0]
		s.close()
		print(ipaddr_check)
		update_code()
		if OLED_connection:
			screen.screen_show(2, 'IP:'+ipaddr_check)
			screen.screen_show(3, 'AP MODE OFF')
	except:
		ap_threading=threading.Thread(target=ap_thread)   #Define a thread for data receiving
		ap_threading.setDaemon(True)                          #'True' means it is a front thread,it would close when the mainloop() closes
		ap_threading.start()                                  #Thread starts
		if OLED_connection:
			screen.screen_show(2, 'AP Starting 10%')
		RL.setColor(0,16,50)
		time.sleep(1)
		if OLED_connection:
			screen.screen_show(2, 'AP Starting 30%')
		RL.setColor(0,16,100)
		time.sleep(1)
		if OLED_connection:
			screen.screen_show(2, 'AP Starting 50%')
		RL.setColor(0,16,150)
		time.sleep(1)
		if OLED_connection:
			screen.screen_show(2, 'AP Starting 70%')
		RL.setColor(0,16,200)
		time.sleep(1)
		if OLED_connection:
			screen.screen_show(2, 'AP Starting 90%')
		RL.setColor(0,16,255)
		time.sleep(1)
		if OLED_connection:
			screen.screen_show(2, 'AP Starting 100%')
		RL.setColor(35,255,35)
		if OLED_connection:
			screen.screen_show(2, 'IP:192.168.12.1')
			screen.screen_show(3, 'AP MODE ON')

async def check_permit(websocket):
	while True:
		recv_str = await websocket.recv()
		cred_dict = recv_str.split(":")
		if cred_dict[0] == "admin" and cred_dict[1] == "123456":
			response_str = "congratulation, you have connect with server\r\nnow, you can do something else"
			await websocket.send(response_str)
			return True
		else:
			response_str = "sorry, the username or password is wrong, please submit again"
			await websocket.send(response_str)

async def recv_msg(websocket):
	global speed_set, modeSelect
	move.setup()
	direction_command = 'no'
	turn_command = 'no'

	while True: 
		response = {
			'status' : 'ok',
			'title' : '',
			'data' : None
		}

		data = ''
		data = await websocket.recv()

		if data == 'heartbeat':
			continue

		try:
			data = json.loads(data)
		except Exception as e:
			print('not A JSON')

		if not data:
			continue

		if isinstance(data,str):
			robotCtrl(data, response)

			switchCtrl(data, response)

			functionSelect(data, response)

			configPWM(data, response)

			if 'get_info' == data:
				response['title'] = 'get_info'
				response['data'] = [info.get_cpu_tempfunc(), info.get_cpu_use(), info.get_ram_info()]

			if 'wsB' in data:
				try:
					set_B=data.split()
					speed_set = int(set_B[1])
				except:
					pass

			elif 'AR' == data:
				modeSelect = 'AR'
				screen.screen_show(4, 'ARM MODE ON')
				try:
					fpv.changeMode('ARM MODE ON')
				except:
					pass

			elif 'PT' == data:
				modeSelect = 'PT'
				screen.screen_show(4, 'PT MODE ON')
				try:
					fpv.changeMode('PT MODE ON')
				except:
					pass

			#CVFL
			elif 'CVFL' == data:
				flask_app.modeselect('findlineCV')

			elif 'CVFLColorSet' in data:
				color = int(data.split()[1])
				flask_app.camera.colorSet(color)

			elif 'CVFLL1' in data:
				pos = int(data.split()[1])
				flask_app.camera.linePosSet_1(pos)

			elif 'CVFLL2' in data:
				pos = int(data.split()[1])
				flask_app.camera.linePosSet_2(pos)

			elif 'CVFLSP' in data:
				err = int(data.split()[1])
				flask_app.camera.errorSet(err)

			elif 'defEC' in data:#Z
				fpv.defaultExpCom()

		elif(isinstance(data,dict)):
			if data['title'] == "findColorSet":
				color = data['data']
				flask_app.colorFindSet(color[0],color[1],color[2])

		if not functionMode:
			if OLED_connection:
				screen.screen_show(5,'Functions OFF')
		else:
			pass

		print(data)
		response = json.dumps(response)
		await websocket.send(response)

async def main_logic(websocket, path):
	await check_permit(websocket)
	try:
		await recv_msg(websocket)
	finally:
		# Safety: never leave the robot moving after the client disconnects.
		try:
			move.motorStop()
		except Exception:
			pass

if __name__ == '__main__':
	switch.switchSetup()
	switch.set_all_switch_off()

	HOST = ''
	PORT = 10223                              #Define port serial 
	BUFSIZ = 1024                             #Define buffer size
	ADDR = (HOST, PORT)

	global flask_app
	flask_app = app.webapp()
	flask_app.startthread()

	try:
		RL=robotLight.RobotLight()
		RL.start()
		RL.breath(70,70,255)
	except:
		print('Use "sudo pip3 install rpi_ws281x" to install WS_281x package\n使用"sudo pip3 install rpi_ws281x"命令来安装rpi_ws281x')
		pass

	while  1:
		wifi_check()
		try:                  #Start server,waiting for client
			start_server = websockets.serve(
				main_logic,
				'0.0.0.0',
				8888,
				ping_interval=WS_PING_INTERVAL,
				ping_timeout=WS_PING_TIMEOUT,
				close_timeout=WS_CLOSE_TIMEOUT
			)
			asyncio.get_event_loop().run_until_complete(start_server)
			print('waiting for connection...')
			# print('...connected from :', addr)
			break
		except Exception as e:
			print(e)
			RL.setColor(0,0,0)

		try:
			RL.setColor(0,80,255)
		except:
			pass
	try:
		asyncio.get_event_loop().run_forever()
	except Exception as e:
		print(e)
		RL.setColor(0,0,0)
		move.destroy()
