import requests

# Low-level API calls
def get_current_stats(base='http://localhost:8089/', timeout=10):
    # Get the current status
    resp = requests.get(base + 'stats/requests', timeout=timeout)
    return resp.json()

def set_target_user_count(locust_count, hatch_rate=50, base='http://localhost:8089/', timeout=10):
    # set the target state
    try:
        resp = requests.post(base+'swarm', data={'locust_count':locust_count, 'hatch_rate': hatch_rate}, timeout=timeout)
        resp_json = resp.json()
        return resp_json['success']
    except:
        return False
    
def stop_test(base='http://localhost:8089/', timeout=10):
    # Stop the test
    resp = requests.get(base+'stop', timeout=timeout)
    try:
        resp_json = resp.json()
        return resp_json['success']
    except:
        return False
    
def reset_stats(base='http://localhost:8089/', timeout=10):
    # reset stats
    resp = requests.get(base+'stats/reset', timeout=timeout)
    if resp.text == 'ok':
        return True
    else:
        return False
    
    
    
    

# Object
import threading
import numpy as np

import time
class TimerClass:
    def __init__(self):
        self.start_time = time.time()

    def tic(self):
        self.start_time = time.time()

    def toc(self):
        elapsed = time.time() - self.start_time
        return elapsed

    def toc_print(self):
        elapsed = time.time() - self.start_time
        print('{:4.02f}'.format(elapsed))
        return elapsed

class WorkerThread(threading.Thread):
    def __init__(self, parent, sleep_time=2):
        super(WorkerThread, self).__init__()
        # if daemon is true this thread will die when the main thread dies
        self.daemon = True
        self.stop_signal = False
        self.sleep_time = sleep_time
        self.loop_timer = TimerClass()
        self.parent = parent
        
    def run(self):
        while not self.stop_signal:
            sleep_time = self.sleep_time
            self.loop_timer.tic()
            try:
                stats = self.parent.get_stats()
                # self.parent.reset_remote_stats()
                
                stats2 = self.parent.custom_sensing()
                if stats2 is not None:
                    for key in stats2:
                        stats["custom_" + str(key)] = stats2[key]
                
                if stats['state'] == 'running':
                    if stats['stats'][0]['num_requests'] > 0:
                        stats['time'] = time.time()
                        self.parent.temp_stats.append(stats)
                        if len(self.parent.temp_stats) > self.parent.temp_stat_max_len:
                            del self.parent.temp_stats[0]
                    else:
                        sleep_time = 0.2
                else:
                    sleep_time = 0.2
            except Exception as e:
                print('Got Exception: ' + str(e))
            elapsed = self.loop_timer.toc()
            if sleep_time - elapsed > 0:
                time.sleep(sleep_time - elapsed)


from datetime import datetime

class DdslLoadTester:
    def __init__(self, base='http://localhost:8089/',hatch_rate=50,temp_stat_max_len=5):
        super(DdslLoadTester, self).__init__()
        self.base = base
        self.hatch_rate = hatch_rate
        self.worker_thread = None
        self.temp_stats = []
        self.temp_stat_max_len = temp_stat_max_len
        
    def get_state(self):
        resp = get_current_stats(self.base)
        return resp['state']
    
    def get_stats(self):
        return get_current_stats(self.base)
    
    def custom_sensing(self):
        return None 
    
    def reset_remote_stats(self):
        return reset_stats(self.base)
        
    def reset_temp_stats(self):
        self.temp_stats = []
#         self.reset_remote_stats()
        return True
    
    def get_temp_stats(self):
        tmp_stats = self.temp_stats
        self.reset_temp_stats()
        return tmp_stats
    
    def set_count(self, new_count):
        return self.change_count(new_count)
    
    def change_count(self, new_count):
        return set_target_user_count(new_count, self.hatch_rate, self.base)
    
    def get_all_stats(self):
        temp_stats = self.get_temp_stats()
                
        return_val = {
            'time': get_stats_arr(temp_stats, 'time'),
            'current_response_time_percentile_50': get_stats_arr(temp_stats, 'current_response_time_percentile_50'),
            'current_response_time_percentile_95': get_stats_arr(temp_stats, 'current_response_time_percentile_95'),
            'current_response_time_average': get_stats_arr(temp_stats, 'current_response_time_average'),
            'current_max_response_time': get_stats_arr(temp_stats, 'current_max_response_time'),
            'current_min_response_time': get_stats_arr(temp_stats, 'current_min_response_time'),
            'fail_ratio': get_stats_arr(temp_stats, 'fail_ratio'),
            'total_rps': get_stats_arr(temp_stats, 'total_rps'),
            'user_count': get_stats_arr(temp_stats, 'user_count'),
            'avg_response_time': get_stats_arr_stats(temp_stats, 'avg_response_time'),
            'current_rps': get_stats_arr_stats(temp_stats, 'current_rps'),
            'max_response_time': get_stats_arr_stats(temp_stats, 'max_response_time'),
            'median_response_time': get_stats_arr_stats(temp_stats, 'median_response_time'),
            'min_response_time': get_stats_arr_stats(temp_stats, 'min_response_time'),
            'num_failures': get_stats_arr_stats(temp_stats, 'num_failures'),
            'num_requests': get_stats_arr_stats(temp_stats, 'num_requests'),
        }
        
        stats2 = self.custom_sensing()
        if stats2 is not None:
            for key in stats2:
                return_val["custom_" + str(key)] = get_stats_arr(temp_stats, "custom_" + str(key))
                        
        return return_val
        
    
    def stop_test(self):
        self.stop_capturing()
        return stop_test(self.base)
    
    def start_capturing(self):
        curr_state = self.get_state()
#         if curr_state != 'running':
#             raise Exception('You should start the test first by calling tester.set_count(). state:' + curr_state)
        
        self.worker_thread = WorkerThread(self)
        self.worker_thread.start()
        
    def prepare_results_from_df(self, results):
        # make the elapsed columns
        results['elapsed'] = (results['time'] - results['time'].min())
        results['elapsed_min'] = results['elapsed']/60

        # Save File
        date = datetime.now()
        filename = "results/" + date.strftime('%Y-%m-%d_%H-%M-%S.csv')
        results.to_csv(filename, index=False)
        return results, filename
        
    def stop_capturing(self):
        if self.worker_thread is not None:
            self.worker_thread.stop_signal = True
            return True
        else:
            return True
        
    def get_plot_filename(self, res):
        date = datetime.now()
        filename = "results/" + date.strftime('%Y-%m-%d_%H-%M-%S.png')
        return filename
        
def get_stats_arr(stats, key):
    return [stats[i][key] for i in range(len(stats))]

def get_stats_arr_stats(stats, key, index=0):
    return [stats[i]['stats'][index][key] for i in range(len(stats))]


seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
def get_loop_time_in_secs(s):
    return int(s[:-1]) * seconds_per_unit[s[-1]]
