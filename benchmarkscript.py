import asyncio
import aiohttp
import time

async def call_endpoint_http1 (session, request_num, dns_name):
    url = f"http://{dns_name}:8000/cluster1"
    headers = {"content-type":"application/json"}
    
    try:
        async with session.get(url, headers = headers) as response:
            status_code = response.status
            response_json = await response.json()
            print (f"Request{ request_num }:Status Code:{ status_code}")
            return status_code, response_json
    except Exception as e :
        print(f"Request{ request_num }:Failed - {str(e)}")
        return None, str(e)


async def call_endpoint_http2(session, request_num, dns_name):
    url = f"http://{dns_name}:8000/cluster2"
    headers = {"content-type": "application/json"}

    try:
        async with session.get(url, headers=headers) as response:
            status_code = response.status
            response_json = await response.json()
            print(f"Request{request_num}:Status Code:{status_code}")
            return status_code, response_json
    except Exception as e:
        print(f"Request{request_num}:Failed - {str(e)}")
        return None, str(e)

def get_load_balancer_dns():
    try:
        with open('load_balancer_dns.txt', 'r') as file:
            dns_name = file.read().strip()
        return dns_name
    except FileNotFoundError:
        print("DNS file not found.")
        return None

async def main () :
    dns_name = get_load_balancer_dns()
    if not dns_name:
        print("No DNS name available for benchmarking.")
        return

    num_requests = 1000
    start_time = time.time()

    print("\nRunning ec2.micro instances\n")
    async with aiohttp . ClientSession () as session :
        tasks = [call_endpoint_http1(session, i, dns_name) for i in range (num_requests)]
        await asyncio.gather(*tasks)

    end_time = time.time()
    print(f"\nTotal time taken: {end_time - start_time:.2f} seconds")
    print(f"Average time per request:{(end_time - start_time)/num_requests:.4f} seconds")

    num_requests = 1000
    start_time = time.time()

    print("\nRunning ec2.large instances\n")
    async with aiohttp.ClientSession() as session:
        tasks = [call_endpoint_http2(session, i, dns_name) for i in range(num_requests)]
        await asyncio.gather(*tasks)

    end_time = time.time()
    print(f"\nTotal time taken: {end_time - start_time:.2f} seconds")
    print(f"Average time per request:{(end_time - start_time) / num_requests:.4f} seconds")

#if __name__ == " __main__ ":
asyncio.run(main ())