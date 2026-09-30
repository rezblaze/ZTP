# from os import read

# working_server_list = []

# with open('labservers', "r") as f:
#     lines = f.readlines()
#     for line in lines:
#         working_server_list.append(line.strip())



# import requests
# import time
# from requests import request
# import urllib3
# import sys
# from threading import Thread
# import concurrent.futures

# urllib3.disable_warnings()

# if len(sys.argv) < 2:
#     print("Abort: Need argument local/sandbox/dev/stage/prod")
#     sys.exit(0)
# if sys.argv[1] == "dev":
#     env = "https://bmi-dev.example.com"
# elif sys.argv[1] == "stage":
#     env = "https://bmi-stage.example.com"
# elif sys.argv[1] == "prod":
#     env = "https://bmi-prod.example.com"
# elif sys.argv[1] == "sandbox":
#     env = "http://lab-bmi-test-01.example.com"
# elif sys.argv[1] == "local":
#     env = "http://127.0.0.1:8080"
# else:
#     print("Valid argument local/sandbox/dev/stage")
#     sys.exit(0)

# serverinfo_ep = "/serverinfo"
# networkdata_ep = "/networkdata"
# adminlo_check = "/bmo/lom/credcheck/adminlo"



# all_results = []

# def get_ep_data(servername, ep):
#     print(f"starting {env}{ep}/{servername}")
#     start_time = time.time()
#     resp = requests.get(f"{env}{ep}/{servername}", verify=False)
#     data = resp.json()
#     duration = time.time() - start_time
#     result = (f"{env}{ep}/{servername}", duration, resp.status_code, resp.json())
#     all_results.append(result)
#     return result


# def get_ep_data_auth(servername, ep):
#     print(f"starting {env}{ep}/{servername}")
#     start_time = time.time()
#     resp = requests.get(f"{env}{ep}/{servername}", verify=False, auth=(user, passwd))
#     data = resp.json()
#     duration = time.time() - start_time
#     result = (f"{env}{ep}/{servername}", duration, resp.status_code, resp.json())
#     all_results.append(result)
#     return result

# def post_to_ep(servername, ep):
#     print(f"starting {env}{ep}/{servername}")
#     start_time = time.time()
#     resp = requests.post(f"{env}{ep}/{servername}", auth=(user, passwd),  verify=False)
#     data = resp.json()
#     duration = time.time() - start_time
#     result = (f"{env}{ep}/{servername}", duration, resp.status_code, resp.json())
#     all_results.append(result)
#     return result


# startime = time.time()
# threds = []

# testing_list = working_server_list

# # for server in testing_list:
# #     ## serverinfo
# #     # t2 = Thread(target=get_ep_data, args=(server.strip(), serverinfo_ep))
# #     # threds.append(t2)

# #     ## adminlo check
# #     t1 = Thread(target=get_ep_data, args=(server.strip(), adminlo_check))
# #     threds.append(t1)

# # [t.start() for t in threds]
# # [t.join() for t in threds]


# # without threading
# # for server in testing_list:
# #     get_ep_data(server.strip(), adminlo_check)

# # Using ThreadPoolExecutor for concurrent requests
# # Note: Adjust max_workers based on your system's capabilities and the server's rate limits.
# # If you encounter issues with too many requests, consider reducing max_workers.
# # If you need to authenticate, replace get_ep_data with get_ep_data_auth or post_to_ep as needed.
# with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
#     # Start the load operations and mark each future with its URL
#     # future_to_get_data = {executor.submit(get_ep_data, server.strip(), networkdata_ep): server for server in testing_list}
#     future_to_get_data = {executor.submit(get_ep_data, server.strip(), serverinfo_ep): server for server in testing_list}
#     # future_to_get_data_3 = {executor.submit(get_ep_data, server.strip(), adminlo_check): server for server in testing_list}
#     # future_to_get_data = { **future_to_get_data_1, **future_to_get_data_2,**future_to_get_data_3}

#     for future in concurrent.futures.as_completed(future_to_get_data):
#         url = future_to_get_data[future]
#         try:
#             data = future.result()
#         except Exception as exc:
#             print('%r generated an exception: %s' % (url, exc))
#         else:
#             print(data)
# print(f"servercount: {len(testing_list)} time: {time.time()-startime}")


# # Save results to CSV
# import csv
# succ_cnt = 0
# fail_cnt = 0
# filename = "output.csv"
# with open(filename, "w") as file:
#     writer = csv.writer(file)
#     for item in all_results:
#         writer.writerow(item)
#         if item[2] == 200:
#             succ_cnt+=1
#         else:
#             fail_cnt+=1
# print(f"response 200: {succ_cnt}, failed: {fail_cnt}")
# print(f"Detail output in {filename}")
