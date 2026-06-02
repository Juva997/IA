import time
start_time = time.time()
sum([x*x for x in range(1000)])
end_time = time.time()
print('Tempo de execucao:', end_time - start_time, 'segundos')