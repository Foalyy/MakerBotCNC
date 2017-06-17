import makerbot_driver
import serial
import serial.tools.list_ports
import threading
import sys

class Makerbot:
    def __init__(self):
        self.condition = threading.Condition()
        self.driver = makerbot_driver.s3g()
        self.connected = False
        self.profileNames = {
            "The Replicator 2" : "Replicator2"
        }

    def connect(self, port, machineName):
        self.port = serial.Serial(port, 115200, timeout=1)
        self.driver.writer = makerbot_driver.Writer.StreamWriter(self.port, self.condition)
        self.connected = True
        self.driver.init()
        self.driver.display_message(0, 0, "********************", 3, False, False, False)
        self.driver.display_message(0, 0, "     Welcome to     ", 3, True, False, False)
        self.driver.display_message(0, 0, "    MakerBotCNC!    ", 3, True, False, False)
        self.driver.display_message(0, 0, "********************", 3, True, True, False)
        #self.driver.queue_song(6)
        if machineName in self.profileNames:
            self.profile = makerbot_driver.Profile(self.profileNames[machineName])
            self.spm = {
                'x' : self.profile.values['axes']['X']['steps_per_mm'],
                'y' : self.profile.values['axes']['Y']['steps_per_mm'],
                'z' : self.profile.values['axes']['Z']['steps_per_mm']
            }
            self.origin = {
                'x' : -190,
                'y' : -43,
                'z' : 100
            }
            self.position = {
                'x' : 0,
                'y' : 0,
                'z' : 0
            }
            self.amplitude = {
                'x' : 0,
                'y' : 0,
                'z' : 0
            }
            for axis in self.origin.keys():
                self.amplitude[axis] = abs(self.origin[axis])
        else:
            raise Exception("Unknown Machine " + machineName)
        self.machinePort = port
        self.machineName = machineName
        print("Connected to machine " + machineName + " on port " + port)

    def autoConnect(self):
        self.connected = False
        machineDetector = makerbot_driver.MachineDetector()
        machineDetector.scan()
        machines = machineDetector.get_available_machines()
        ports = machines.keys()
        for port in ports:
            machineName = machineDetector.get_machine_name_from_vid_pid(machines[port]["VID"], machines[port]["PID"])
            if machineName != None:
                try:
                    self.connect(port, machineName)
                except Exception as e:
                    raise e
                if self.connected:
                    break

    def home(self):
        # Move Z lower
        self.driver.set_extended_position([0, 0, 0, 0, 0])
        self.driver.queue_extended_point_classic([0, 0, 5000, 0, 0], 300)
        self.wait()

        # Home X/Y quickly
        self.driver.find_axes_maximums(['x', 'y'], 200, 60)
        self.driver.set_extended_position([0, 0, 0, 0, 0])
        
        # Home X/Y more slowly
        self.driver.queue_extended_point_classic([-500, -500, 0, 0, 0], 400)
        self.driver.find_axes_maximums(['x', 'y'], 2000, 60)
        self.driver.set_extended_position([0, 0, 0, 0, 0])

        # Home Z quickly
        self.driver.find_axes_minimums(['z'], 100, 60)
        self.driver.set_extended_position([0, 0, 0, 0, 0])

        # Home Z more slowly
        self.driver.queue_extended_point_classic([0, 0, 1000, 0, 0], 300)
        self.driver.find_axes_minimums(['z'], 1000, 60)
        self.driver.set_extended_position([0, 0, 0, 0, 0])
        self.wait()

        # Ask the user to tighten the screws
        raw_input("Please tighten the levelling screws under the buildplate")

        # Lower the buildplate a bit
        self.driver.queue_extended_point_classic([0, 0, 20000, 0, 0], 100)
        #self.wait()

        # Go to origin
        self.position = {
            'x' : 0,
            'y' : 0,
            'z' : 0
        }
        self._move(100)
        self.wait()

    def move(self, x, y, speed=300, relative=False):
        if relative:
            self.position['x'] += x
            self.position['y'] += y
        else:
            self.position['x'] = x
            self.position['y'] = y

        # Check for boundaries
        #if self.position['x'] < 0:
        #    self.position['x'] = 0
        #elif self.position['x'] > abs(self.origin['x']):
        #    self.position['x'] = abs(self.origin['x'])
        #if self.position['y'] < 0:
        #    self.position['y'] = 0
        #elif self.position['y'] > abs(self.origin['y']):
        #    self.position['y'] = abs(self.origin['y'])

        # Move
        self._move(speed)

    def moveZ(self, z, speed=100, relative=False):
        if relative:
            self.position['z'] += z
        else:
            self.position['z'] = z

        # Check for boundaries
        if self.position['z'] < 0:
            self.position['z'] = 0
        if self.position['z'] > abs(self.origin['z']):
            self.position['z'] = abs(self.origin['z'])

        # Move
        self._move(speed)

    def _move(self, speed):
        position = [(self.position['x'] + self.origin['x']) * self.spm['x'],
                    (self.position['y'] + self.origin['y']) * self.spm['y'],
                    (self.origin['z'] - self.position['z']) * self.spm['z'], 0, 0]
        self.driver.queue_extended_point_classic(position, speed)
        self.release(['z'])

    def wait(self):
        try:
            while not self.driver.is_finished():
                pass
        except:
            self.stop()
            sys.exit(0)

    def hold(self, axes=['x','y','z']):
        self.wait()
        self.driver.toggle_axes(axes, True)

    def release(self, axes=['x','y','z']):
        self.wait()
        self.driver.toggle_axes(axes + ['a', 'b'], False)

    def stop(self):
        self.driver.abort_immediately()

    def isConnected(self):
        return self.connected
