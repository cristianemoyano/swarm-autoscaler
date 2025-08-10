from multiprocessing.dummy import Pool as ThreadPool
import threading
import time
import statistics
import logging
from discovery import Discovery
from decrease_mode_enum import DecreaseModeEnum

from docker_service import DockerService
from constants import (
    MetricEnum,
    metric_to_str,
    LABEL_MIN_REPLICAS,
    LABEL_MAX_REPLICAS,
    DEFAULT_MIN_REPLICAS,
    DEFAULT_MAX_REPLICAS,
)
from queue import Queue, Empty

class AutoscalerService(threading.Thread):
    def __init__(self, swarmService: DockerService, discovery: Discovery, checkInterval: int, minPercentage: int, maxPercentage: int):
        threading.Thread.__init__(self)
        self.swarmService = swarmService
        self.discovery = discovery
        self.checkInterval = checkInterval
        self.minPercentage = minPercentage
        self.maxPercentage = maxPercentage
        self.autoscaleServicePool = ThreadPool(8)
        self.logger = logging.getLogger("AutoscalerService")
        # Scale requests queue and worker to serialize scale operations
        self._scaleQueue: Queue = Queue(maxsize=1000)
        self._pendingActions = {}
        self._pendingLock = threading.Lock()
        self._scaleWorker = _ScaleWorker(self.swarmService, self._scaleQueue, self._pendingActions, self._pendingLock)
        self._scaleWorker.daemon = True
        self._scaleWorker.start()
        # Track last observed autoscalable services count to avoid noisy logs
        self._lastServiceCount = None
 
    def run(self):
        """
        Run the thread
        """
        while True:
            try:
                if(not self.swarmService.isLeader()):
                    self.logger.warning("Instance running not on manager or not on leader")
                    time.sleep(60*10) # Wait 10 minute
                    continue
                # Evaluate all services that define autoscale label (true/false)
                services = self.swarmService.getServicesWithAutoscaleLabel()
                services = services if services is not None else []
                cur_count = len(services)
                if self._lastServiceCount is None or cur_count > self._lastServiceCount:
                    if self._lastServiceCount is None:
                        self.logger.info("Services for autoscaling: %s", cur_count)
                    else:
                        self.logger.info("Services for autoscaling increased: %s -> %s", self._lastServiceCount, cur_count)
                    self._lastServiceCount = cur_count
                # Don't block on slower services; process as results come in
                list(self.autoscaleServicePool.imap_unordered(self.__autoscale, services))
            except Exception as e:
                self.logger.error("Error in autoscale thread", exc_info=True)
            time.sleep(self.checkInterval)

    def __autoscale(self, service):
        serviceMetric = self.swarmService.getServiceMetric(service, MetricEnum.CPU)
        cpuLimit = self.swarmService.getServiceCpuLimitPercent(service) if serviceMetric == MetricEnum.CPU else -1
        containers = self.swarmService.getServiceContainersId(service)

        if(containers == None or len(containers) == 0):
            self.logger.warning("No running tasks in service (%s) found" %service.name)
            return

        stats = []
        metric_key = metric_to_str(serviceMetric)
        for id in containers:
            containerStats = self.discovery.getContainerStats(id, cpuLimit, metric_key)
            if(containerStats != None and metric_key in containerStats):
                stats.append(containerStats[metric_key])
        if(len(stats) > 0):
            self.__scale(service, stats, metric_key)

    def __scale(self, service, stats, metric_name: str):
        """
            Calculate median and max metric percentage of service replicas and inc or dec replicas count
        """
        meanValue = statistics.median(stats)
        maxValue = max(stats)

        serviceMaxPercentage = self.swarmService.getServiceMaxPercentage(service, self.maxPercentage)
        serviceMinPercentage = self.swarmService.getServiceMinPercentage(service, self.minPercentage)
        serviceDecreaseMode = self.swarmService.getServiceDecreaseMode(service)

        self.logger.debug("Metric=%s | Service=%s | Mean=%s | Max=%s", metric_name, service.name, meanValue, maxValue)
            
        try:
            autoscale_enabled = self.swarmService.isAutoscaleEnabled(service)

            # Current replicas and bounds
            labels = (service.attrs.get('Spec', {}) or {}).get('Labels', {}) or {}
            replicated = (service.attrs.get('Spec', {}) or {}).get('Mode', {}).get('Replicated') or {}
            replicas = int(replicated.get('Replicas', 0))
            minReplicas = int(labels.get(LABEL_MIN_REPLICAS, DEFAULT_MIN_REPLICAS))
            maxReplicas = int(labels.get(LABEL_MAX_REPLICAS, DEFAULT_MAX_REPLICAS))

            scale_up_needed = meanValue > serviceMaxPercentage
            scale_down_threshold = (meanValue if serviceDecreaseMode == DecreaseModeEnum.MEDIAN else maxValue)
            scale_down_needed = scale_down_threshold < serviceMinPercentage

            # Respect replica bounds early to avoid enqueue noise
            if scale_up_needed and replicas >= maxReplicas:
                self.logger.debug("Service %s at max replicas (%s); skipping scale up", service.name, maxReplicas)
                scale_up_needed = False
            if scale_down_needed and replicas <= minReplicas:
                self.logger.debug("Service %s at min replicas (%s); skipping scale down", service.name, minReplicas)
                scale_down_needed = False

            if scale_up_needed:
                reason = f"{metric_name} median {meanValue:.1f}% > max {serviceMaxPercentage}%"
                if not autoscale_enabled:
                    self.logger.warning("Service %s would scale up to %s but autoscale=false. %s", service.name, replicas+1, reason)
                else:
                    self._enqueue_scale(service, True, reason, metric_name)
            elif scale_down_needed:
                comp = scale_down_threshold
                basis = "median" if serviceDecreaseMode == DecreaseModeEnum.MEDIAN else "max"
                reason = f"{metric_name} {basis} {comp:.1f}% < min {serviceMinPercentage}%"
                if not autoscale_enabled:
                    self.logger.warning("Service %s would scale down to %s but autoscale=false. %s", service.name, max(replicas-1, minReplicas), reason)
                else:
                    self._enqueue_scale(service, False, reason, metric_name)
            else:
                self.logger.debug("Service %s not needed to scale", service.name)
        except Exception as e:
            self.logger.error("Error while try scale service", exc_info=True)

    def _enqueue_scale(self, service, scaleIn: bool, reason: str, metric_name: str) -> None:
        service_id = service.id
        with self._pendingLock:
            last = self._pendingActions.get(service_id)
            if last is not None and last == scaleIn:
                # Duplicate action already pending; skip
                return
            self._pendingActions[service_id] = scaleIn
        try:
            self._scaleQueue.put_nowait((service_id, scaleIn, reason, metric_name))
            self.logger.debug("Enqueued scale action for %s: %s", service.name, 'up' if scaleIn else 'down')
        except Exception:
            # Queue full or unexpected error; drop gracefully
            self.logger.warning("Scale queue is full. Dropping scale action for %s", service.name)


class _ScaleWorker(threading.Thread):
    def __init__(self, swarmService: DockerService, scaleQueue: Queue, pendingActions: dict, pendingLock: threading.Lock):
        super().__init__()
        self.swarmService = swarmService
        self.scaleQueue = scaleQueue
        self.pendingActions = pendingActions
        self.pendingLock = pendingLock
        self.logger = logging.getLogger("ScaleWorker")

    def run(self):
        while True:
            try:
                service_id, scaleIn, reason, metric_name = self.scaleQueue.get(timeout=1.0)
            except Empty:
                continue
            try:
                # Refresh service reference before scaling
                service = self.swarmService.dockerClient.services.get(service_id)
                self.swarmService.scaleService(service, scaleIn, reason=reason, metric=metric_name)
            except Exception:
                self.logger.error("Failed to scale service id=%s", service_id, exc_info=True)
            finally:
                with self.pendingLock:
                    # Clear pending action regardless of result to allow future attempts
                    if service_id in self.pendingActions:
                        del self.pendingActions[service_id]
                self.scaleQueue.task_done()
