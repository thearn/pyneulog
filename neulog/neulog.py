import serial
import platform
import time
import os

MAX_TYPE = chr(34)
MAX_ID = chr(9)
ACK = chr(11)
STX_4SAMP = chr(17)
STX_USB = chr(18)
USB_LEARN = chr(96)
WRITE_TO_EE = chr(45)
START_SAMPLE = chr(46)
STOP_SAMPLE = chr(47)
IN_READ = chr(49)
READ_PARAMETERS = chr(50)
READ_RAM = chr(53)
SEN_LIST = chr(71)
EXP_SAMPLES = chr(73)
EXP_TRIGGER = chr(74)
TX_4_EE = chr(78)
START_UPLOAD = chr(83)
STX = chr(85)
RESERVED_FOR_STX = chr(85)
START_SAMPLE_GROUP = chr(86)
FINISH_UPLOAD = chr(88)

def bcd(l):
    if [255, 255, 255] == l: return '-'
    num = ''
    for i in l:
        t = i / 16
        if 10 == t: t = '.'
        elif 11 == t: t = '+'
        elif 12 == t: t = '-'
        elif 13 == t: t = ' '
        else: t = str(t)
        num = num + t
        t = i % 16
        if 10 == t: t = '.'
        elif 11 == t: t = '+'
        elif 12 == t: t = '-'
        elif 13 == t: t = ' '
        else: t = str(t)
        num = num + t
    return num.strip()

class Device(serial.Serial):
    def __init__(self, port = None):
        if not port:
            port = self.get_port()
        serial.Serial.__init__(
            self,
            port = port,
            baudrate = 115200,
            parity = serial.PARITY_NONE,
            stopbits = serial.STOPBITS_TWO,
            bytesize = serial.EIGHTBITS,
            timeout = 1
        )
        self.status = 'connected'
        self.buf = []

    def get_port(self):
        return detect_device()
        """
        osname = platform.system()
        if osname == "Darwin":
            port = "/dev/tty.SLAB_USBtoUART"
        else:
            port = "COM5"
        """

    def send(self, s, checksum = False):
        time.sleep(0.02)
        self.flushInput()
        self.flushOutput()
        for c in s:
            self.write(c)
        if checksum:
            self.write(chr(sum([ord(c) for c in s]) % 256))

    def receive(self, i = False):
        time.sleep(0.02)
        iw = self.inWaiting()
        if False == i: i = iw
        if iw >= i:
            #print "reading %i out of %i" % (i, iw)
            r = self.read(i)
            return r
        return 'False'

    def connect(self):
        self.close()
        self.open()
        self.send(STX + 'NeuLog!')
        if 'OK-V' != self.receive(4): return False
        self.status = 'connected'
        return '.'.join([str(ord(c)) for c in self.receive(3)])

    def scanStart(self):
        if self.status != 'connected': return False
        self.send(STX_USB + USB_LEARN + MAX_TYPE + MAX_ID, True)
        r = self.receive(4)
        print "What's this: %i" % (ord(r[-1]))
        if STX_USB + USB_LEARN + ACK == r[:-1]:
            self.status = 'scanning'
            return True
        return False

    def scanRead(self):
        if self.status != 'scanning': return False
        sensors = []
        r = self.receive()
        while len(r) > 7:
            chunk, r = r[:8], r[8:]
            if STX != chunk[0]: continue
            chunk = [ord(c) for c in chunk]
            if chunk[-1] != sum(chunk[:-1]) % 256: continue
            stype, sid, ssndver = chunk[1:4]
            sver = '.'.join([str(i) for i in chunk[4:7]])
            sensors.append((stype, sid, sver))
        return sensors

    def scanStop(self):
        if self.status != 'scanning': return False
        self.send(STX_USB)
        self.receive()
        self.status = 'connected'
        return True

    def eeread(self, stype, sid, add):
        if self.status[:7] == 'running': return False
        self.send(STX + stype + sid + READ_PARAMETERS + chr(0) + add + chr(0), True)
        t = self.receive()
        if t[0:4] != STX + stype + sid + READ_PARAMETERS:
            #FIXME This sometimes returns nothing
            print 'Did not get response from eeread, will keep on trying'
            return self.eeread(stype, sid, add)
            raise Exception('Sensor did not acknowledge');
        return [ord(c) for c in t[4:7]]

    def eewrite(self, stype, sid, add, val):
        if self.status[:7] == 'running': return False
        self.send(STX + stype + sid + WRITE_TO_EE + chr(0) + add + val, True)
        if self.receive()[0:5] != STX + stype + sid + WRITE_TO_EE + ACK:
            raise Exception('Sensor did not acknowledge');

    def getSensorRange(self, stype, sid):
        if self.status != 'connected': return False
        return self.eeread(chr(stype), chr(sid), chr(11))[0];

    def setSensorRange(self, stype, sid, val):
        if self.status != 'connected': return False
        self.eewrite(chr(stype), chr(sid), chr(11), chr(val))
        return True

    def getSensorsData(self, stype, sid):
        if self.status != 'connected': return False
        self.send(STX + chr(stype) + chr(sid) + IN_READ + (3 * chr(0)), True)
        r = self.receive()
        if not r or STX != r[0] or IN_READ != r[3]: return False
        r = [ord(c) for c in r]
        if r[-1] != sum(r[:-1]) % 256: return False
        return bcd(r[4:7])

    def expStart(self, rate, timebase, samples, sensors, online):
        if self.status != 'connected': return False
        self.status = 'preparing'
        self.send(STX + (2 * chr(0)) + STOP_SAMPLE + (3 * chr(0)), True)

        if 2 == timebase: fast = 1
        else: fast = 0

        # Get params from first sensor
        if not online:
            s = sensors[0]
            stype = chr(s[0])
            sid = chr(s[1])

            d = self.eeread(stype, sid, chr(72))
            rate = d[0] * 256 + d[1]
            if 0 == d[2]:
                rate *= 0.01
            elif 2 == d[2]:
                rate *= 0.0001

            d = self.eeread(stype, sid, chr(79))
            samples = d[0] * 256 + d[1]

        # Sensors, like many other things in NeuLog, are enumerated from 1
        i = 1
        for s in sensors:
            stype = chr(s[0]);
            sid = chr(s[1]);

            # Sensor list
            self.send(STX_USB + SEN_LIST + chr(i) + stype + sid + chr(1), True)
            if self.receive()[0:4] != STX_USB + SEN_LIST + chr(i) + ACK:
                raise Exception('Sensor did not acknowledge');
            i += 1

            # Mark sensor as participant
            self.eewrite(stype, sid, chr(14), chr(1))

            # Sensor options
            if online:
                self.eewrite(stype, sid, chr(2), chr(rate / 256))
                self.eewrite(stype, sid, chr(3), chr(rate % 256))
                self.eewrite(stype, sid, chr(4), chr(timebase))
                self.eewrite(stype, sid, chr(5), chr(0))
                self.eewrite(stype, sid, chr(6), chr(0))
                self.eewrite(stype, sid, chr(7), chr(0))
                self.eewrite(stype, sid, chr(8), chr(0))
                self.eewrite(stype, sid, chr(9), chr(samples / 256))
                self.eewrite(stype, sid, chr(10), chr(samples % 256))
                self.eewrite(stype, sid, chr(12), chr(fast))

        self.send(STX_USB + EXP_SAMPLES + chr(samples / 256) + chr(samples % 256), True)
        if self.receive()[0:3] != STX_USB + EXP_SAMPLES + ACK:
            raise Exception('Sensor did not acknowledge');

        if online:
            self.send(STX_USB + EXP_TRIGGER + (7 * chr(0)), True)
            if self.receive()[0:3] != STX_USB + EXP_TRIGGER + ACK:
                raise Exception('Sensor did not acknowledge');
            self.send(STX_USB + START_SAMPLE, True)
            if self.receive(4)[0:3] != STX_USB + START_SAMPLE + ACK:
                raise Exception('Sensor did not acknowledge');
            self.status = 'runningOnline'
        else:
            self.send(STX_USB + START_UPLOAD, True)
            if self.receive(4)[0:3] != STX_USB + START_UPLOAD + ACK:
                raise Exception('Sensor did not acknowledge');
            self.status = 'runningOffline'

        return True

    def expStop(self):
        if self.status[:7] != 'running': return False
        self.send(STX + (2 * chr(0)) + STOP_SAMPLE + (3 * chr(0)), True)
        self.status = 'connected'
        return True

    def getSamples(self):
        if self.status[:7] != 'running': return False
        samples = []
        updates = []
        self.buf += self.receive()

        if len(self.buf) > 3 and self.buf[0] == STX_USB:
            if self.buf[1] in [STOP_SAMPLE, FINISH_UPLOAD] and self.buf[2] == ACK:
                self.status = 'connected'
                samples.append('done')
            else:
                print 'USB said: ', [ord(c) for c in self.buf]
            self.buf = self.buf[4:]

        while len(self.buf) > 18 and len(samples) < 100:
            if self.buf[0] == STX_4SAMP and self.buf[3] == TX_4_EE:
                stype = ord(self.buf[1])
                sid = ord(self.buf[2])
                dat = [bcd([ord(c) for c in self.buf[i:i+3]]) for i in range(6, 16, 3)]
                samples.append([stype, sid, dat])

                self.buf = self.buf[19:]
            elif self.buf[0] == STX and self.buf[3] == READ_RAM:
                stype = ord(self.buf[1])
                sid = ord(self.buf[2])
                dat = bcd([ord(c) for c in self.buf[4:7]])
                updates.append([stype, sid, dat])
                self.buf = self.buf[8:]
            else:
                print "!!LOST %i" % (ord(self.buf[0]))
                self.buf = self.buf[1:]

        return [samples, updates]

def scan():
    # scan for available ports. return a list of tuples (num, name)
    if platform.system() == "Darwin":
        import glob
        return glob.glob('/dev/tty.S*')
    else:

        available = []
        for i in range(256):
            try:
                s = serial.Serial(i)
                available.append( s.portstr)
                s.close()
            except serial.SerialException:
                pass
        return available

def detect_device():
    ports = scan()
    for port in ports:
        d = Device(port = port)
        try:
            #d = float(d.getSensorsData(16,1))
            if d.connect():
                return port
        except:
            pass


class gsr(object):

    def __init__(self):
        self.device = Device()
        t = time.time()
        while not self.device.connect(): 
            if time.time() - t > 2:
                break

    def get_data(self):
        return float(self.device.getSensorsData(16,1))

if __name__ == '__main__':
    d = gsr()
    while True:
        print d.get_data()
