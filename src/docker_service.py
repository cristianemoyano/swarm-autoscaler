#!/bin/python
import docker
import logging
import time
from docker.errors import APIError
from cache import Cache
from constants import (
    LABEL_AUTOSCALE,
    LABEL_MAX_REPLICAS,
    LABEL_MIN_REPLICAS,
    LABEL_DISABLE_MANUAL_REPLICAS,
    LABEL_PERCENTAGE_MAX,
    LABEL_PERCENTAGE_MIN,
    LABEL_DECREASE_MODE,
    LABEL_METRIC,
    DEFAULT_MIN_REPLICAS,
    DEFAULT_MAX_REPLICAS,
)
from constants import MetricEnum
from decrease_mode_enum import DecreaseModeEnum

class DockerService(object):
    AutoscaleLabel = LABEL_AUTOSCALE
    MaxReplicasLabel = LABEL_MAX_REPLICAS
    MinReplicasLabel = LABEL_MIN_REPLICAS
    DisableManualReplicasControlLabel = LABEL_DISABLE_MANUAL_REPLICAS
    MaxPercentageLabel = LABEL_PERCENTAGE_MAX
    MinPercentageLabel = LABEL_PERCENTAGE_MIN
    DecreaseModeLabel = LABEL_DECREASE_MODE
    MetricLabel = LABEL_METRIC  # cpu | memory (default: cpu)

    def __init__(self, memoryCache: Cache, dryRun: bool):
        self.memoryCache = memoryCache
        self.dryRun = dryRun
        self.dockerClient = docker.from_env()
        self.nodeInfo = self.dockerClient.info()
        self.logger = logging.getLogger("DockerService")

    def isManager(self):
        try:
            self.dockerClient.nodes.list()
            return True
        except:
            return False

    def isLeader(self):
        if(not self.isManager()):
            return False
        nodeList = self.dockerClient.nodes.list(filters={'role': 'manager'})
        nodeAddr = self.nodeInfo['Swarm']['NodeAddr']
        managerLeader = list(x for x in nodeList if x.attrs['ManagerStatus'].get('Leader'))[0]
        return managerLeader.attrs['ManagerStatus']['Addr'].startswith(nodeAddr)

    def getAutoscaleServices(self):
        allServices = self.dockerClient.services.list(filters={'label':self.AutoscaleLabel})
        if(len(allServices) == 0):
            return None
        enabledAutoscaleServices = list((x for x in allServices if x.attrs['Spec']['Labels'][self.AutoscaleLabel] == 'true'))
        return enabledAutoscaleServices

    def getServiceContainersId(self, service):
        tasks = service.tasks({'desired-state':'running'})
        if(len(tasks) == 0):
            return None
        return list((x['Status']['ContainerStatus']['ContainerID'] for x in tasks if x['Status'].get('ContainerStatus') != None)) # Get container Id's only for running containers

    def getServiceCpuLimitPercent(self, service):
        try:
            return service.attrs.get('Spec').get('TaskTemplate').get('Resources').get('Limits').get('NanoCPUs')/10000000/100
        except:
            return -1.0

    def getServiceMaxPercentage(self, service, default = None):
        try:
            return int(service.attrs.get('Spec').get('Labels').get(self.MaxPercentageLabel))
        except:
            return default

    def getServiceMinPercentage(self, service, default = None):
        try:
            return int(service.attrs.get('Spec').get('Labels').get(self.MinPercentageLabel))
        except:
            return default

    def getServiceDecreaseMode(self, service, default = DecreaseModeEnum.MEDIAN):
        try:
            return DecreaseModeEnum[service.attrs.get('Spec').get('Labels').get(self.DecreaseModeLabel).upper()]
        except:
            return default

    def getServiceMetric(self, service, default: MetricEnum = MetricEnum.CPU):
        try:
            value = service.attrs.get('Spec').get('Labels').get(self.MetricLabel)
            from constants import parse_metric  # local import to avoid cycles
            return parse_metric(value)
        except:
            return default

    def getContainerCpuStat(self, containerId, cpuLimit):
        containers = self.dockerClient.containers.list(filters={'id':containerId})
        if(len(containers) == 0):
            return None
        containerStats = containers[0].stats(stream=False)
        return self.__calculateCpu(containerStats, cpuLimit)

    def getContainerMemoryStat(self, containerId):
        containers = self.dockerClient.containers.list(filters={'id':containerId})
        if(len(containers) == 0):
            return None
        containerStats = containers[0].stats(stream=False)
        return self.__calculateMemory(containerStats)

    def scaleService(self, service, scaleIn = True):
        replicated = service.attrs['Spec']['Mode'].get('Replicated')
        if(replicated == None):
            self.logger.error("Cannot scale service %s because is not replicated mode", service.name)
            return
        
        maxReplicasPerNode = self.__getServiceMaxReplicasPerNode(service)
        nodeCount = self.__getNodesCountCached()

        maxReplicas = service.attrs['Spec']['Labels'].get(self.MaxReplicasLabel)
        maxReplicas = DEFAULT_MAX_REPLICAS if maxReplicas == None else int(maxReplicas)

        minReplicas = service.attrs['Spec']['Labels'].get(self.MinReplicasLabel)
        minReplicas = DEFAULT_MIN_REPLICAS if minReplicas == None else int(minReplicas)

        disableManualReplicas = service.attrs['Spec']['Labels'].get(self.DisableManualReplicasControlLabel) == 'true'

        replicas = replicated['Replicas']
        newReplicasCount = replicas + 1 if scaleIn else replicas - 1
        if(maxReplicasPerNode != None and maxReplicasPerNode != 0 and (nodeCount * maxReplicasPerNode) < newReplicasCount):
            self.logger.warning("There is no required number of nodes to host service (%s) instances. Nodes: %s. MaxReplicasPerNode: %s", service.name, nodeCount, maxReplicasPerNode)
            return

        if(disableManualReplicas):
            if(newReplicasCount < minReplicas):
                newReplicasCount = minReplicas
            if(newReplicasCount > maxReplicas):
                newReplicasCount = maxReplicas

        if(replicas == newReplicasCount):
            self.logger.debug('Replicas count not changed for the service (%s)', service.name)
            return

        if(newReplicasCount < minReplicas or newReplicasCount > maxReplicas):
            self.logger.debug('The limit for decreasing (%s) or increasing (%s) the number of instances for the service (%s) has been reached. NewReplicasCount: %s',
            minReplicas, maxReplicas, service.name, newReplicasCount)
            return

        self.logger.info("Scale service %s to %s",service.name, newReplicasCount)

        if(self.dryRun):
            return

        # Retry on swarm "update out of sequence" transient error
        attempts = 0
        last_err = None
        while attempts < 3:
            try:
                # Refresh service reference before each attempt
                fresh_service = self.dockerClient.services.get(service.id)
                fresh_service.scale(newReplicasCount)
                return
            except APIError as e:
                last_err = e
                msg = str(e).lower()
                if "update out of sequence" in msg or "update in progress" in msg:
                    self.logger.warning("Retrying service update due to transient error: %s", e)
                    attempts += 1
                    time.sleep(1.0 * attempts)
                    continue
                raise
        # If all retries failed, re-raise last error for visibility
        if last_err:
            raise last_err
        
    def __calculateCpu(self, stats, cpuLimit):
        try:
            cpu_stats = stats.get('cpu_stats', {})
            precpu_stats = stats.get('precpu_stats', {})

            # Determine cpu count robustly
            cpuCount = cpu_stats.get('online_cpus')
            if not cpuCount:
                per_cpu = ((cpu_stats.get('cpu_usage') or {}).get('percpu_usage')) or []
                cpuCount = len(per_cpu) if isinstance(per_cpu, list) and len(per_cpu) > 0 else 1

            cpu_usage_total = ((cpu_stats.get('cpu_usage') or {}).get('total_usage')) or 0.0
            precpu_usage_total = ((precpu_stats.get('cpu_usage') or {}).get('total_usage')) or 0.0
            system_cpu = cpu_stats.get('system_cpu_usage') or 0.0
            pre_system_cpu = precpu_stats.get('system_cpu_usage') or 0.0

            cpuDelta = float(cpu_usage_total) - float(precpu_usage_total)
            systemDelta = float(system_cpu) - float(pre_system_cpu)

            percent = 0.0
            if cpuDelta > 0.0 and systemDelta > 0.0:
                percent = (cpuDelta / systemDelta) * float(cpuCount) * 100.0

            # Normalize by CPU limit or cpuCount
            if cpuLimit and cpuLimit > 0:
                percent = percent / float(cpuLimit)
            else:
                percent = percent / float(cpuCount if cpuCount > 0 else 1)
            return percent
        except Exception:
            return 0.0

    def __calculateMemory(self, stats):
        try:
            memoryStats = stats.get('memory_stats', {})
            usage = float(memoryStats.get('usage', 0.0))
            limit = float(memoryStats.get('limit', 0.0))
            if limit <= 0.0:
                return 0.0
            percent = (usage / limit) * 100.0
            return percent
        except Exception:
            return 0.0

    def __getNodesCountCached(self):
        cacheKey = "nodes_count"
        nodesCount = self.memoryCache.get(cacheKey)
        if ( nodesCount != None ):
            return nodesCount
        return self.memoryCache.set(cacheKey, len(self.dockerClient.nodes.list()), 30)

    def __getServiceMaxReplicasPerNode(self, service):
        try:
            return service.attrs.get('Spec').get('TaskTemplate').get('Placement').get('MaxReplicas')
        except:
            return None
