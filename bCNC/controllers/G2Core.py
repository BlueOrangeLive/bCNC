# G2Core motion controller plugin

from __future__ import absolute_import
from __future__ import print_function
from _GenericController import _GenericController
from _GenericController import POSPAT, TLOPAT, DOLLARPAT
from CNC import CNC

import time
import json


class Controller(_GenericController):
	def __init__(self, master):
		self.gcode_case = 1
		self.has_override = False
		self.master = master
		print("G2Core loaded")

	def hardResetPre(self):
		self.master.serial_write(b"\030")

	def hardResetAfter(self):
		time.sleep(6)
		self.initController()	# Required to reload values

	def viewBuild(self):
		self.master.serial_write(b'{"sys":n}')

	def grblHelp(self):
		self.master.serial_write(b"%\n")

	def softReset(self, clearAlarm=True):
		# Don't do this, it resets all the config values in firmware.
		# if self.master.serial:
			# self.master.serial_write(b"\030")
		self.master.stopProbe()
		if clearAlarm: self.master._alarm = False

		# 0	INITIALIZING	Machine is initializing
		# 1	READY	Machine is ready for use
		# 2	ALARM	Machine is in alarm state
		# 3	PROGRAM_STOP	Machine has encountered program stop
		# 4	PROGRAM_END	Machine has encountered program end
		# 5	RUN	Machine is running
		# 6	HOLD	Machine is holding
		# 7	PROBE	Machine is in probing operation
		# 8	CYCLE	reserved for canned cycles (not used)
		# 9	HOMING	Machine is in a homing cycle
		# 10	JOG	Machine is in a jogging cycle
		# 11	INTERLOCK	Machine is in safety interlock hold
		# 12	SHUTDOWN	Machine is in shutdown state. Will not process commands
		# 13	PANIC	Machine is in panic state. Needs to be physically reset
				# "Idle"		: "Yellow",
				# "Run"		: "LightGreen",
				# "Alarm"		: "Red",
				# "Jog"		: "Green",
				# "Home"		: "Green",
				# "Check"		: "Magenta2",
				# "Sleep"		: "LightBlue",
				# "Hold"		: "Orange",
				# "Hold:0"	: "Orange",
				# "Hold:1"	: "OrangeRed",
				# "Queue"		: "OrangeRed",
				# "Door"		: "Red",
				# "Door:0"	: "OrangeRed",
				# "Door:1"	: "Red",
				# "Door:2"	: "Red",
				# "Door:3"	: "OrangeRed",
				# CONNECTED	: "Yellow",
				# NOT_CONNECTED	: "OrangeRed"

	def mapState(self,state):
		states = [ "Idle", "Idle", "Alarm", "Idle", "Idle", "Run", "Hold",
			"Run", "Run", "Home", "Jog", "Door", "Alarm", "Alarm" ]
		return states[state]

	def setState(self, stat):
		try:
			state = self.mapState(stat)
			if CNC.vars["state"] != state or self.master.runningPrev != self.master.running:
				self.master.controllerStateChange(state)
			self.master.runningPrev = self.master.running

			self.displayState(state)
		except:
			pass

	def processStatusReport(self, sr):
		if "stat" in sr:
			self.setState(sr["stat"])
		try:
			if "feed" in sr:
				CNC.vars["curfeed"] = float(sr["feed"])
			# if "vel" in sr:
			# 	CNC.vars["curvel"] = float(sr["vel"])
			# "line" comes back, but only matters if gcode has it.
			# spindle does not.  Nor a responds from gcode changing.
			# "tool" in theory could return haven't seen it.
			# "units",  "coor" come back
			if "unit" in sr:
				CNC.vars["unit"] = float(sr["unit"])
			if "posx" in sr:
				CNC.vars["mx"] = float(sr["posx"]) #( relative!)
			if "posy" in sr:
				CNC.vars["my"] = float(sr["posy"])# mposx is absolute machine
			if "posz" in sr:
				CNC.vars["mz"] = float(sr["posz"])
			CNC.vars["wx"] = round(CNC.vars["mx"]-CNC.vars["wcox"], CNC.digits)
			CNC.vars["wy"] = round(CNC.vars["my"]-CNC.vars["wcoy"], CNC.digits)
			CNC.vars["wz"] = round(CNC.vars["mz"]-CNC.vars["wcoz"], CNC.digits)
			self.master._posUpdate = True
		except:
			print("Problem parsing status report")
			pass

	def processErrorReport(er):
		fb = er["fb"]
		st = er["st"]
		msg = er["msg"]
		self.master.log.put((self.master.MSG_ERROR, msg))

	def processFooter(self,f):
		revision, status, lines_available = f
		# self.setState(status)  NO, THIS IS A DIFFERENT STATUS.

	def parseValues(self, values):
		if "sr" in values:
			self.processStatusReport(values["sr"])
		if "err" in values:
			self.processErrorReport(values["er"])
		if "f" in values:
			self.processFooter(values["f"])
		if "r" in values:
			self.parseValues(values["r"])
		else:
			# print(values)
			k = list(values.keys())
			if len(k) > 0 and k[0][0] == 'g':
				gcodenum = int(k[0][1:3])
				gcode = k[0][0:3].upper()
				if gcodenum in ( 28,30,54,55,56,57,58,59,92 ):
					CNC.vars[gcode+"X"] = values[k[0]]['x']
					CNC.vars[gcode+"Y"] = values[k[0]]['y']
					CNC.vars[gcode+"Z"] = values[k[0]]['z']
					# CNC.vars[gcode+"U"] = values[k[0]]['u']
					# CNC.vars[gcode+"V"] = values[k[0]]['v']
					# CNC.vars[gcode+"W"] = values[k[0]]['w']
					# CNC.vars[gcode+"A"] = values[k[0]]['a']
					# CNC.vars[gcode+"B"] = values[k[0]]['b']
					# CNC.vars[gcode+"C"] = values[k[0]]['c']

	def parseLine(self, line, cline, sline):
		# print("Parsing:",line, cline, sline)
		if not line:
			return True

		elif line[0]=='{':
			self.master.log.put((self.master.MSG_RECEIVE, line))
			values = json.loads(line)
			if "r" in values:
				# print(self.master.sio_status)
				if not self.master.sio_status:
					self.master.log.put((self.master.MSG_OK, line))
					self.master._gcount += 1
					if cline: del cline[0]
					if sline: del sline[0]
			# if "sr" in values:
				self.master.sio_status = False
			self.parseValues(values)

		else:
			#We return false in order to tell that we can't parse this line
			#Sender will log the line in such case
			return False

		# Machine is Idle buffer is empty stop waiting and go on
		if (
			self.master.sio_wait
			and not cline
			and CNC.vars["state"] == "Idle"
		):
			self.master.sio_wait = False
			self.master._gcount += 1

		#Parsing succesful
		return True

	def purgeController(self):
		self.master.serial_write(b"!\004\n")
		self.master.serial.flush()
		time.sleep(1)
		# remember and send all G commands
		G = " ".join([x for x in CNC.vars["G"] if x[0] == "G"])  # remember $G
		TLO = CNC.vars["TLO"]
		self.softReset(False)  # reset controller
		self.purgeControllerExtra()
		self.master.runEnded()
		self.master.stopProbe()
		if G:
			self.master.sendGCode(G)  # restore $G
		self.master.sendGCode(f"G43.1Z{TLO}")  # restore TLO
		self.viewState()


	def viewStatusReport(self):
		# Don't actually need to send this, because we'll get an
		# automatic report if anything changes
		# Except for at M2 end of gcode, because nothing updates status :(
		# self.master.serial_write(b"?\n")
		self.master.serial_write(b"{sr:n}\n")
		self.master.sio_status = True
		pass

	def viewParameters(self):
		self.master.sendGCode("$$\n")
		# self.master.sendGCode('{"sr":n}\n')

	def viewState(self): #Maybe rename to viewParserState() ???
		# self.master.sendGCode('{"sr":n}\n')
		self.master.serial_write('{"sr":n}\n')

# Recognized single character commands are:
# ! - Feedhold request
# ~ - Feedhold exit (restart)
# % - Queue flush
# ^d - Kill job (ASCII 0x04)
# ^x - Reset board (ASCII 0x18)
# ENQ - Enquire communications status (ASCII 0x05)
