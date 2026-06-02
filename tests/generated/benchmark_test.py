import time
start = time.time()
sum([x for x in range(100)])
time.sleep(2)
elapsed = (time.time() - start)