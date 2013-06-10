from neulog import gsr
from gzp import save
import time

"""
Sample GSR experiment.

Gathers data over two phases. Use a keyboard interrupt (control-c) to end a phase.

Saves data to disk afterwards.
"""

sensor = gsr()

data = []
times = []
t0 = time.time()

print "First phase..."
while True: #first phase (eg. 'resting')
    try:
        x = sensor.get_data()
        t = time.time() - t0
        print t, x
        data.append(x)
        times.append(t)
    
    except KeyboardInterrupt:
        break

breaktime = time.time() - t0

print "Second phase..."
while True: #second phase (eg. 'attentive')
    
    try:
        x = sensor.get_data()
        t = time.time() - t0
        print t, x
        data.append(x)
        times.append(t)
    
    except KeyboardInterrupt:
        break

print "Done - saving to disk ('experiment.dat')"
save([data, times, breaktime], "experiment.dat")