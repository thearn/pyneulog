from neulog import gsr
from gzp import save
import time

sensor = gsr()

data = []
times = []
t0 = time.time()

while True: #resting 
    try:
        x = gsr.get_data()
        t = time.time() - t0
        
        data.append(x)
        times.append(t)
    
    except KeyboardInterrupt:
        break

breaktime = time.time() - t0

while True: #active
    
    try:
        x = gsr.get_data()
        time.time() - t0
        
        data.append(x)
        times.append(t)
    
    except KeyboardInterrupt:
        break

save([data, times, breaktime], "experiment.dat")