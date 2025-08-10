#!/bin/python
import os
import socket
from requests import get
import json
from cache import Cache
from multiprocessing.dummy import Pool as ThreadPool
from settings import DISCOVERY_WORKERS

class Discovery(object):
    DiscoveryCacheKey = "discovery_hosts"
    def __init__(self, discoveryDnsName, memoryCache: Cache, checkInterval: int):
        # Tunable concurrency for node discovery requests
        self.threadPool = ThreadPool(max(1, DISCOVERY_WORKERS))
        self.cache = memoryCache
        self.cacheTime = checkInterval / 2
        self.discoveryName = discoveryDnsName
        self.addrInfoExpectedType = socket.SOCK_STREAM
        if(os.name == 'nt'):
            self.addrInfoExpectedType = 0

    def getContainerStats(self, containerId, cpuLimit, metric: str = 'cpu'):
        query = "/api/container/stats?id=%s" % containerId
        if metric == 'cpu':
            query += "&cpuLimit=%s" % cpuLimit
        query += "&metric=%s" % metric
        return self.__sendToAll(query)

    def __sendToAll(self, url):
        hosts = self.__getClusterHosts()
        requests = list("http://%s%s" %(ip,url) for ip in hosts)
        # Return as soon as the first successful response arrives
        for result in self.threadPool.imap_unordered(self.__send, requests):
            if result is not None:
                return result
        return None

    def __send(self, url):
        try:
            result = get(url, timeout=3.0)
            if result is not None and result.status_code == 200:
                return json.loads(result.text)
        except Exception:
            pass
        return None

    def __getClusterHosts(self):
        cachedHosts = self.cache.get(self.DiscoveryCacheKey)
        if(cachedHosts != None):
            return cachedHosts
        
        hosts = []
        dnsResult = socket.getaddrinfo(self.discoveryName, 80)
        for info in dnsResult:
            if(info[0] == socket.AF_INET and info[1] == self.addrInfoExpectedType):
                hosts.append(info[4][0])

        return self.cache.set(self.DiscoveryCacheKey, hosts, self.cacheTime)
